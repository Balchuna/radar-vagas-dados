# Decisões

Todas tomadas em 12/11/2026, na ordem em que apareceram.

## Fontes e coleta

1. **Só APIs públicas de quadros de vagas: Greenhouse, Lever e Ashby.** São os endpoints que as próprias empresas usam para mostrar as vagas no site. Não exigem login nem chave. Li os termos e o `robots.txt` de cada uma antes de usar ([FONTES.md](FONTES.md)).

2. **Gupy descartada.** Os termos de uso para candidatos proíbem "agregar, copiar ou duplicar" partes da plataforma, e montar uma base semanal de vagas é agregar. Há dúvida se a regra vale para quem consulta sem conta, mas, na dúvida, ficou de fora. O custo é real: a Gupy concentra muitas vagas júnior de empresas brasileiras (ver Limitações no README).

3. **LinkedIn fora.** Os termos proíbem coleta automatizada. Os scripts antigos de LinkedIn não foram usados nem reescritos.

4. **A base antiga serviu só como mapa.** Uma coleta exploratória de outubro mostrou quais empresas usam cada fonte e o formato das respostas. Nenhum script dela foi copiado. A lista de 31 empresas ([config/empresas.yaml](../config/empresas.yaml)) é a das empresas cujo quadro respondeu e tinha ao menos uma vaga no Brasil ou na América Latina na sondagem de 12/11/2026.

5. **Coleta educada.** User-Agent com o nome do projeto e sem dado pessoal; no máximo 1 requisição por segundo por host; timeout de 30 s; até 4 tentativas com espera crescente (2, 4 e 8 s) só para falha de rede ou erro 5xx. 403 ou 429 encerra aquela fonte na execução, sem tentar contornar. As demais empresas da fonte ficam registradas como "pulada".

6. **O texto da descrição não é guardado.** As descrições pertencem às empresas e o projeto não precisa delas depois de extrair as skills. O banco guarda metadados, as skills, o link e um hash SHA-256 do texto, que mostra se a descrição mudou sem guardá-la.

7. **Vaga Ashby com `isListed: false` é descartada.** A documentação da Ashby diz que essas vagas só devem ser acessadas por link direto.

8. **Vagas "banco de talentos" são descartadas.** "Talent pool", "cadastro reserva" e parecidos não são vagas e inflariam as contagens.

## Normalização e banco

9. **Área e nível pelo título, modalidade pela fonte ou pela descrição.** O título é o campo mais padronizado entre as três fontes. A modalidade vem, nessa ordem, do campo da fonte, do local ou título ("Remote - Brazil") e, por último, da descrição. A origem fica gravada (`modalidade_origem`) para medir quanto depende da descrição.

10. **Skills por dicionário versionado, com bordas.** Cada skill tem sinônimos em português e inglês. A busca exige que o termo não esteja colado a letra ou número (`(?<![\w+#])` e `(?![\w+#])`), o que evita "SQL" em "MySQLi" e mantém "C#" e "C++". "R" e "Go" diferenciam maiúsculas e só contam em contextos como "Python ou R" ou "Golang". "Python" conta também Pandas, PySpark e NumPy, que são bibliotecas de Python.

11. **Dicionário versão 2, depois de uma auditoria.** Li os trechos em que cada skill foi encontrada nas 439 vagas de dados e TI da primeira coleta e corrigi os falsos positivos:
    - "Inferência" sozinha (que pegava "inferência de modelos em produção") saiu de Estatística;
    - "Experimentação" sozinha (que pegava "drive experimentation") saiu de Testes A/B;
    - GTM (que pegava "GTM Engineering", de vendas) saiu de Google Analytics;
    - "Agile" e "Ágil" sozinhos (que pegavam "stay agile") saíram de Scrum/Ágil;
    - "Macros" sozinho (que pegava as macros do dbt) saiu de VBA.

    Algumas skills mudaram de nome para dizer o que contam: Excel/planilhas, ETL/pipelines de dados, Data Warehouse/Lake. Cada falso positivo virou um teste em `tests/test_skills.py`.

12. **Skill que sai do dicionário sai do banco.** Ao sincronizar, o programa apaga as skills que não estão mais no dicionário e os vínculos delas. As vagas ainda abertas recebem as skills novas na coleta seguinte. As vagas já encerradas perdem a skill e não ganham a nova, porque a descrição não está guardada para reprocessar. É o preço da decisão 6, e está nas limitações.

13. **UPSERT com `ON CONFLICT`, e vaga que some fica inativa.** A chave é (fonte, id da vaga na fonte). A vaga vista de novo atualiza a linha e a data da última vez vista. A vaga que não aparece na coleta da empresa recebe `ativa = 0` e não é apagada, para dar para medir quanto tempo as vagas ficam abertas. Se a empresa falhar (erro de rede), nada dela é desativado.

## Análises

14. **Um arquivo SQL com todas as contas.** [sql/analises.sql](../sql/analises.sql) tem um bloco por pergunta, marcado com `-- nome:`. O Python só executa e formata. Assim, cada número do README aponta para uma consulta que dá para ler.

15. **Banco aberto só para leitura nas análises.** As visões auxiliares são temporárias (`CREATE TEMP VIEW`) e somem ao fechar a conexão. Um teste confirma que o arquivo do banco não muda depois das análises.

16. **Pergunta ampliada, com o recorte "entrada ou sem nível".** Na primeira coleta, só 2 das 97 vagas de dados diziam estágio ou júnior no título; na coleta final de 12/11/2026, só 1 das 95 (`python scripts/relatorio.py`). Uma análise só de vagas júnior não teria amostra. Por escolha do autor, o projeto analisa as vagas de dados de todos os níveis e compara o grupo "estágio, júnior ou sem nível no título" com "pleno para cima". A limitação está declarada: "sem nível" não garante que a vaga aceite iniciantes.

17. **Margem de erro de 95% nas comparações entre níveis.** A diferença entre duas proporções tem margem aproximada de `1,96 × raiz(p1(1−p1)/n1 + p2(1−p2)/n2)`. Com grupos de 34 e 61 vagas, a margem passa de 15 pontos percentuais na maioria das skills. Só a diferença maior que a margem vira frase na página. Não é um teste formal: serve para não vender ruído como achado.

18. **Comparação por nível só para skills com 10 vagas de dados ou mais.** Abaixo disso, a porcentagem de cada grupo muda muito com uma vaga a mais ou a menos.

19. **Semana começa na segunda-feira, em UTC.** `date(x, 'weekday 0', '-6 days')` leva qualquer data para a segunda-feira da semana. A evolução semanal só vira gráfico a partir da segunda semana de coleta.

## Página

20. **Página estática gerada pelo Python, com Chart.js por cima.** As tabelas vêm prontas no HTML e a página funciona sem JavaScript. Se o Chart.js não carregar, as tabelas se abrem sozinhas. O Chart.js 4.4.1 vem do cdnjs com verificação de integridade (SRI).

21. **A página não tem hora de geração.** Só a data da coleta. Gerar duas vezes sobre o mesmo banco dá o mesmo arquivo, byte a byte (há teste para isso). Assim, o cron só commita quando os dados mudam.

22. **Texto das vagas sempre escapado.** Títulos vêm de fora e passam por `html.escape` nas tabelas. No JSON embutido, `</` vira `<\/`, para um título com `</script>` não quebrar a página. Há teste com esse título.

23. **Cores validadas para daltonismo, nos modos claro e escuro.** A paleta tem azul, laranja e verde-água. O verde-água tem contraste abaixo de 3:1 no fundo claro; por isso todo gráfico tem legenda e tabela, e a cor nunca é o único jeito de ler o número.

## Coleta automática

24. **Uma vez por semana, segunda-feira às 10:17 UTC.** As vagas mudam devagar, e a análise é semanal. Uma coleta por semana dá cerca de 31 requisições por semana no total.

25. **O banco viaja como artefato, não como commit.** O banco tem os títulos e links de todas as vagas, e o repositório precisa só dos agregados. A cada execução, o workflow baixa o banco da última execução bem-sucedida, coleta, gera a página, sobe o banco de novo (guardado por 90 dias) e commita só `docs/index.html` e `docs/dados/agregados.json`. Se o artefato sumir (mais de 90 dias sem coleta), a série recomeça do zero.

26. **Coleta sem nenhuma empresa respondendo falha de propósito.** `scripts/coletar.py` sai com erro, o workflow para e não publica uma página sem coleta nova.
