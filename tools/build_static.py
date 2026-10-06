"""Gera uma versão estática (sem login) do artefato Indicadores CAE Club.

Uso: python3 build_static.py <artefato.html> <pasta_db> <saida.html>
A pasta_db tem as coleções exportadas do banco do artefato (meses, polos,
ranking, conversaoVendedor), um JSON por documento.
"""
import json, re, sys, pathlib, datetime

src, dbdir, out = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
html = pathlib.Path(src).read_text(encoding="utf-8")

# A página de verdade começa no <!DOCTYPE html> interno (o arquivo salvo vem com um invólucro).
start = html.find("<!DOCTYPE html>")
end = html.rfind("</html>", 0, html.rfind("</html>")) + len("</html>") if html.count("</html>") > 1 else len(html)
page = html[start:end] if start >= 0 else html

snap = {}
for coll in sorted(p for p in dbdir.iterdir() if p.is_dir()):
    snap[coll.name] = [{"id": f.stem, "data": json.loads(f.read_text(encoding="utf-8"))}
                       for f in sorted(coll.glob("*.json"))]

gerado = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime("%d/%m/%Y às %H:%M")

shim = """
/* ---- versão estática: dados embutidos no lugar do banco do artefato ---- */
const SNAP = %s;
const SNAP_GERADO = %s;
function snapDb() {
  const mk = (id, data) => ({id, exists: true, data: () => data});
  const cmp = {"==": (a, b) => a === b, ">=": (a, b) => a >= b, "<=": (a, b) => a <= b, ">": (a, b) => a > b, "<": (a, b) => a < b};
  const q = (c, filters, order) => {
    const run = () => {
      let docs = (SNAP[c] || []).filter(d => filters.every(([f, op, v]) => cmp[op](d.data[f], v)));
      if (order) docs = [...docs].sort((a, b) => (a.data[order[0]] > b.data[order[0]] ? 1 : -1) * (order[1] === "desc" ? -1 : 1));
      return {docs: docs.map(d => mk(d.id, d.data))};
    };
    return {
      where: (f, op, v) => q(c, [...filters, [f, op, v]], order),
      orderBy: (f, dir) => q(c, filters, [f, dir || "asc"]),
      onSnapshot: cb => { setTimeout(() => cb(run())); return () => {}; },
      get: () => Promise.resolve(run())
    };
  };
  return {
    collection: c => q(c, [], null),
    doc: path => {
      const [c, id] = path.split("/"); const d = (SNAP[c] || []).find(x => x.id === id);
      const snap = d ? mk(id, d.data) : {id, exists: false, data: () => null};
      return {onSnapshot: cb => { setTimeout(() => cb(snap)); return () => {}; }, get: () => Promise.resolve(snap)};
    }
  };
}
""" % (json.dumps(snap, ensure_ascii=False), json.dumps(gerado))

old = 'try { db = await window.claude?.use?.("db"); } catch (e) { db = null; }'
assert old in page, "trecho do banco não encontrado"
page = page.replace(old, "db = snapDb();")
page = page.replace("<script>", "<script>" + shim, 1)

# Rodapé: deixa claro que é uma foto dos dados.
page = page.replace('<footer id="foot"></footer>',
                    '<footer id="foot"></footer><p class="nota" style="margin-top:8px">Versão de consulta gerada em '
                    + gerado + '.</p>')
pathlib.Path(out).write_text(page, encoding="utf-8")
print("ok", out, len(page), "bytes;", {k: len(v) for k, v in snap.items()})
