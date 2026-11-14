# Fontes: termos de uso e robots.txt

Antes de usar cada fonte, li os termos de uso e o `robots.txt` dela. Verificação feita em **12/11/2026**. Isto é o registro do que encontrei, não um parecer jurídico.

Regras que valem para todas as fontes usadas (em `src/radar/http.py`):

- User-Agent `radar-vagas-dados/0.1 (projeto de portfolio; ...)`, sem nome nem e-mail de pessoa;
- no máximo 1 requisição por segundo por host, com timeout de 30 s;
- falha temporária (rede ou erro 5xx) é tentada até 4 vezes no total, com espera de 2, 4 e 8 s entre as tentativas;
- resposta 403 ou 429 encerra a fonte naquela execução, sem tentar contornar;
- uma requisição por empresa por execução (cerca de 31 por semana no total);
- o texto completo das descrições **não é guardado**: só metadados, as skills extraídas, um hash (SHA-256) do texto e o link da vaga.

## Resumo

| Fonte | Endpoint | robots.txt | Termos | Decisão |
|---|---|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{empresa}/jobs?content=true` | Libera tudo, exceto `/embed/` | API pública, sem chave; nada proíbe | **Usada** |
| Lever | `api.lever.co/v0/postings/{empresa}?mode=json` | `Allow: /`, `Crawl-delay: 1` | API pública; o README diz que as vagas publicadas podem ser coletadas por terceiros | **Usada** |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{empresa}` | `api.ashbyhq.com/robots.txt` responde 401 (não há arquivo público) | API pública, sem chave; nada proíbe | **Usada** |
| Gupy | `portal.gupy.io/api/job-search/jobs` (não documentado) | Libera tudo | Os termos proíbem "agregar, copiar ou duplicar" partes da plataforma | **Descartada** |
| LinkedIn | não usado | não consultado | Os termos proíbem coleta automatizada | **Fora**, decidido antes da coleta |

## Greenhouse

- Documentação: https://developers.greenhouse.io/job-board.html (redireciona para https://docs.greenhouse.io/job-board.html).
- Diz que os dados do Job Board são públicos e que os endpoints GET não exigem autenticação. Não documenta limite de requisições. Não encontrei cláusula contra coleta automatizada.
- Termos do site: https://www.greenhouse.com/legal (contratos voltados a clientes; não há termos específicos para a API pública).
- robots.txt (https://boards-api.greenhouse.io/robots.txt): `User-agent: *` / `Disallow: /embed/`. O projeto usa `/v1/boards/...`, que está liberado.

## Lever

- Documentação: https://github.com/lever/postings-api
- O README diz que a API serve para montar sites de vagas e que as vagas publicadas são públicas e "podem ser coletadas por terceiros". O único limite citado é para envio de candidaturas (POST), que o projeto não usa.
- Termos: https://www.lever.co/terms-of-service (atualizados em 25/08/2023). As restrições ali valem para clientes da Lever, não para a leitura de vagas públicas.
- robots.txt (https://api.lever.co/robots.txt): `User-agent: *` / `Allow: /` / `Crawl-delay: 1`. O intervalo de 1 s do projeto respeita o `Crawl-delay`.
- O robots.txt de `jobs.lever.co` traz sinais de conteúdo `search=yes, ai-train=no, use=reference`. O projeto não usa esse host para coletar e não treina modelo de IA com as vagas.

## Ashby

- Documentação: https://developers.ashbyhq.com/docs/public-job-posting-api
- A API devolve as vagas publicadas de uma empresa, sem chave. Não documenta limite de requisições. Não encontrei proibição de coleta.
- A documentação avisa que vaga com `isListed: false` só deve ficar acessível por link direto. **O projeto descarta essas vagas.**
- Termos: https://www.ashbyhq.com/terms (de clientes, atualizados em 29/09/2025).
- robots.txt: `https://api.ashbyhq.com/robots.txt` responde HTTP 401 (não existe arquivo público). O de `jobs.ashbyhq.com` bloqueia só `/meeting/`, `/b/` e `/api/`; o projeto não usa esse host.
- Observação: a coleta antiga de outubro recebeu 403 em todas as empresas da Ashby. Com o User-Agent do projeto, as mesmas URLs responderam 200. Se voltar a dar 403, a fonte é encerrada naquela execução, como manda a regra.

## Gupy (descartada)

- O portal usa `https://portal.gupy.io/api/job-search/jobs`, que não é documentado. O `robots.txt` (https://portal.gupy.io/robots.txt) libera tudo.
- Os **Termos de Uso do Gupy Recrutamento e Seleção — Pessoas Candidatas**, versão de 01/07/2026 (https://www.gupy.io/termos-de-uso-recrutamento-e-selecao-candidatos), na lista "É proibido à Pessoa Candidata (e aos Usuários em geral no que se aplica)", incluem **"agregar, copiar ou duplicar partes do Gupy Recrutamento e Seleção, incluindo oportunidades de trabalho expiradas"**. Montar uma base semanal de vagas é exatamente agregar.
- A API oficial (https://developers.gupy.io) existe, mas é só para empresas clientes dos planos Premium e Enterprise, com token.
- Há dúvida se esses termos valem para quem só consulta o portal sem conta. Na dúvida, a fonte ficou de fora. O custo disso está nas limitações do README: a Gupy concentra muitas vagas de nível júnior de empresas brasileiras.

## LinkedIn (fora)

Os termos do LinkedIn proíbem coleta automatizada. A base antiga tinha scripts para o LinkedIn; eles não foram usados nem reescritos.
