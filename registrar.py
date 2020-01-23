import asyncio
import csv
import json
import sys

import httpx

modalidades = {}
cursos = {}
notas = {}

def values_sep(f, sep=':', comment='#'):
    for line in f.readlines():
        line = line.strip().split(comment)[0]
        if not line:
            continue

        yield [s.strip() for s in line.split(sep)]

with open('notas.txt') as f:
    for mat, nota in values_sep(f):
        nota = float(nota.replace(',', '.'))
        notas[mat.lower()] = nota

with open('modalidades.txt') as f:
    for mod, desc in values_sep(f):
        modalidades[int(mod)] = desc

with open('cursos.txt') as f:
    for curso_id, desc in values_sep(f):
        cursos[int(curso_id)] = desc

async def get_data(curso, modalidades=modalidades, notas=notas, client=None):
    close = client is None
    if close:
        client = httpx.AsyncClient()

    r = await client.get(f'https://sisu-api.apps.mec.gov.br/api/v1/oferta/{curso}/modalidades')
    data = json.loads(r.content)

    total_s = 0
    total_p = 0
    for mat, nota in notas.items():
        peso = float(data['oferta'][f'nu_peso_{mat}'])
        total_s += peso * nota
        total_p += peso
    total = round(total_s / total_p, 2)

    corte = {}
    for mod in data['modalidades']:
        mod_c = int(mod['co_concorrencia'])
        if mod_c not in modalidades:
            continue
        assert mod['qt_vagas'] == mod['qt_vagas_concorrencia']
        vagas = mod['qt_vagas'] if int(mod['qt_vagas']) != 0 else ''
        n_corte = mod['nu_nota_corte'] if float(mod['nu_nota_corte']) != 0 else ''
        if not vagas and not n_corte:
            continue
        corte[mod_c] = (n_corte, vagas)

    if close:
        await client.aclose()

    return curso, total, corte


async def collect():
    async with httpx.AsyncClient() as client:
        coros = []
        for curso in cursos:
            coros.append(get_data(curso, client=client))
        return await asyncio.gather(*coros)

data = asyncio.run(collect())

with open(sys.argv[1], 'w') as f:
    csv_w = csv.writer(f)
    for curso, nota, mods in data:
        csv_w.writerow(['Curso:', cursos[curso]])
        csv_w.writerow(['Sua nota:', nota])
        for mod in mods:
            notac, vagas = mods[mod]
            csv_w.writerow([f'Nota de corte {modalidades[mod]}:', notac])
            csv_w.writerow([f'Vagas {modalidades[mod]}:', vagas])
        csv_w.writerow([])
