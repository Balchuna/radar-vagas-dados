# Como funciona

Este texto explica o projeto sem jargão. Os detalhes técnicos estão no código e em [DECISOES.md](DECISOES.md).

## A ideia

Muitas empresas publicam as vagas abertas num "quadro de vagas" mantido por uma empresa de recrutamento: Greenhouse, Lever ou Ashby. Esses quadros têm um endereço público que devolve a lista de vagas num formato que o computador lê direto (uma API). É o mesmo dado que aparece na página "Trabalhe conosco" da empresa.

O projeto pergunta a esses endereços, uma vez por semana, quais vagas estão abertas em 31 empresas. Guarda o resumo de cada vaga num banco de dados e, a partir dele, conta quais skills as vagas de dados pedem.

## O caminho de uma vaga

1. **Pergunta educada.** O programa chama o endereço de cada empresa, uma de cada vez, com no máximo uma chamada por segundo em cada site. Ele se identifica como "radar-vagas-dados (projeto de portfólio)". Se o site responder "proibido" (403) ou "devagar" (429), o programa para de chamar aquele site até a próxima semana. Antes de usar cada site, li os termos de uso e o `robots.txt` dele ([FONTES.md](FONTES.md)).
2. **Só Brasil e América Latina.** Vagas com local nos Estados Unidos ou na Europa são descartadas. Vagas "banco de talentos" (sem vaga real por trás) também.
3. **Leitura do título.** Pelo título, o programa decide a área (dados, TI ou outra) e o nível (estágio, júnior, pleno, sênior, liderança ou não informado). "Analista de Dados Júnior" vira dados e júnior. "Data Engineer" vira dados, nível não informado.
4. **Leitura da descrição.** A descrição é lida só na memória, para achar as skills e a modalidade (remoto, híbrido ou presencial). Depois é descartada: o banco guarda só um "resumo digital" (hash) do texto, que serve para saber se a descrição mudou, sem guardar o texto.
5. **Skills por dicionário.** Um arquivo ([config/skills.yaml](../config/skills.yaml)) lista 65 skills e os jeitos de escrever cada uma: "Power BI", "PowerBI"; "Excel", "planilhas". O programa procura esses termos no título e na descrição. Ele exige que o termo esteja isolado: "SQL" não conta dentro de "MySQLi".
6. **Banco de dados.** Cada vaga vira uma linha no banco (SQLite, um arquivo só). A vaga é identificada pela fonte e pelo número que a fonte dá a ela.

## Rodar duas vezes não duplica nada

Quando a mesma vaga aparece de novo, o programa **atualiza** a linha existente em vez de criar outra. Ele anota a data em que viu a vaga pela última vez. Se uma vaga que estava aberta não aparece mais, ela é marcada como encerrada (não é apagada). Se voltar, é reaberta.

Isso tem nome técnico (UPSERT idempotente), mas a ideia é simples: rodar a coleta duas vezes seguidas deixa o banco igual. O comando `python scripts/conferir_idempotencia.py` faz duas coletas reais seguidas e compara o banco depois de cada uma.

## Das vagas aos números

Todas as contas estão num arquivo só, [sql/analises.sql](../sql/analises.sql). Cada pergunta é uma consulta com nome: "skills mais pedidas", "modalidade", "Power BI x Looker x Tableau" e assim por diante. O comando `python scripts/relatorio.py`:

- abre o banco **só para leitura** (as contas não podem alterar os dados);
- roda cada consulta;
- calcula a margem de erro das comparações entre níveis;
- grava a página [docs/index.html](index.html) e os números em [docs/dados/agregados.json](dados/agregados.json);
- imprime tudo no terminal.

Os números do README e do currículo saem desse comando.

## O recorte "vagas de entrada"

Quase nenhuma vaga dessas empresas diz "júnior" no título. Por isso o projeto compara dois grupos:

- **entrada ou sem nível:** estágio, júnior ou título sem nível. São as que, em tese, aceitam quem está começando;
- **pleno para cima:** pleno, sênior ou liderança.

"Sem nível no título" não quer dizer "aceita júnior". Muitas dessas vagas pedem anos de experiência na descrição. É uma aproximação, e o README diz isso.

## A margem de erro

Com 34 vagas num grupo e 61 no outro, uma diferença de 15 pontos percentuais pode ser acaso. Para cada skill, o relatório calcula a margem de erro aproximada (95%) da diferença entre os dois grupos. Só a diferença maior que a margem vira frase na página. As outras ficam na tabela, marcadas como "não".

## A página

A página mostra a data da coleta no topo, os números principais, gráficos e tabelas. As tabelas já vêm prontas do Python, então a página funciona mesmo sem JavaScript. Os gráficos são desenhados por cima, com a biblioteca Chart.js. A página não registra a hora em que foi gerada: rodar o relatório de novo sobre o mesmo banco produz o mesmo arquivo, byte a byte.

## A coleta automática

O arquivo [.github/workflows/coleta.yml](../.github/workflows/coleta.yml) faz a coleta toda segunda-feira no GitHub Actions:

1. roda os testes;
2. baixa o banco da semana anterior (guardado como "artefato", fora do repositório);
3. coleta;
4. gera a página;
5. guarda o banco de novo;
6. commita só a página e o JSON, se mudaram.

O banco não vai para o repositório. Ele tem os títulos e os links de todas as vagas, e o que interessa publicar são os números agregados.
