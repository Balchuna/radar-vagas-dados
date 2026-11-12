# Estudo: 10 perguntas prováveis de entrevista

Respostas curtas, baseadas no que este projeto realmente faz. Os números são da coleta de 12/11/2026 e saem de `python scripts/relatorio.py` (ver "Resultados" no README).

## 1. O que é o projeto, em uma frase?

Um coletor em Python que lê, uma vez por semana, as vagas abertas de 31 empresas nas APIs públicas do Greenhouse, da Lever e da Ashby, guarda o resumo de cada vaga em SQLite e mostra, numa página, quais skills as vagas de dados pedem e o que muda nas vagas para quem está começando.

## 2. Por que essas fontes? Você podia coletar esses dados?

Porque são endpoints públicos que as próprias empresas usam para mostrar as vagas no site, sem login nem chave. Antes de usar cada fonte, li os termos de uso e o `robots.txt` e registrei com os links em `docs/FONTES.md`. Duas fontes ficaram de fora pelos termos: a Gupy, que proíbe "agregar, copiar ou duplicar" partes da plataforma, e o LinkedIn, que proíbe coleta automatizada. A Gupy faz falta, porque tem muitas vagas júnior de empresas brasileiras, e isso está nas limitações.

## 3. Como a coleta se comporta com o site do outro lado?

Com quatro cuidados: o programa se identifica no User-Agent como projeto de portfólio, sem dado pessoal; faz no máximo 1 requisição por segundo em cada site; toda requisição tem timeout de 30 s; e falha de rede ou erro 5xx é tentada até 4 vezes, com espera de 2, 4 e 8 s. Se o site responder 403 (proibido) ou 429 (devagar), o programa para de chamar aquela fonte até a próxima execução, sem tentar contornar. Tudo isso tem teste, com uma sessão HTTP falsa e um relógio falso.

## 4. O que é um UPSERT idempotente e como você provou que funciona?

UPSERT é "insere ou atualiza": a vaga tem uma chave única (fonte, id da vaga na fonte), e o `INSERT ... ON CONFLICT DO UPDATE` atualiza a linha quando a vaga já existe. Idempotente quer dizer que rodar duas vezes dá o mesmo resultado que rodar uma. A vaga que some recebe `ativa = 0` e não é apagada. A prova foi `scripts/conferir_idempotencia.py`: duas coletas reais seguidas, com uma "impressão digital" do banco depois de cada uma. Em 12/11/2026, as duas deram `612ef11b278e8dac`: 1.508 vagas, 1.505 ativas e 3.831 vínculos vaga-skill. A segunda coleta teve 0 novas e 0 desativadas.

## 5. Por que você não guarda o texto das vagas?

Porque o texto pertence às empresas e o projeto só precisa dele para extrair as skills e a modalidade. A descrição é lida na memória e descartada. O banco guarda metadados, as skills, o link e um hash SHA-256 do texto, que mostra se a descrição mudou sem guardá-la. O custo: quando o dicionário de skills muda, as vagas já encerradas não podem ser reprocessadas.

## 6. Como as skills são encontradas? Como você evitou falsos positivos?

Por um dicionário versionado (`config/skills.yaml`, 65 skills), com os jeitos de escrever cada uma em português e inglês. A busca exige que o termo esteja isolado: "SQL" não conta dentro de "MySQLi", e "C#" é encontrado com o símbolo. Depois da primeira coleta, li os trechos em que cada skill foi encontrada nas 439 vagas de dados e TI e achei falsos positivos: "GTM" pegava "GTM Engineering", que é de vendas, e "Agile" pegava "stay agile". Corrigi o dicionário (versão 2), e cada falso positivo virou um teste.

## 7. Como estão organizadas as contas em SQL?

Num arquivo só, `sql/analises.sql`, com um bloco por pergunta, marcado com `-- nome:`. Um bloco de preparo cria visões temporárias (`CREATE TEMP VIEW`): vagas ativas, vagas de dados e vagas de dados com skill. O banco é aberto só para leitura, e um teste confirma que o arquivo não muda. Um exemplo é a consulta `bi_combinacoes`: um `LEFT JOIN` mantém as vagas sem nenhuma skill, `MAX(skill = 'Power BI')` marca cada ferramenta por vaga e um `CASE` separa "só Power BI", "duas ou mais" e "nenhuma das três". Sem o `LEFT JOIN`, as 66 vagas que não citam nenhuma das três (69,5%) sumiriam da conta.

## 8. Por que a pergunta mudou de "vagas júnior" para "todos os níveis"?

Porque quase nenhuma vaga de dados diz "júnior" no título: na coleta final, só 1 das 95, e era de estágio. Uma análise só de vagas júnior não teria amostra. Então comparei dois grupos: "estágio, júnior ou sem nível no título" (34 vagas) e "pleno para cima" (61). A limitação fica declarada: "sem nível" não garante que a vaga aceite iniciantes.

## 9. Como você sabe que uma diferença entre os grupos não é acaso?

Para cada skill, calculo a margem de erro aproximada de 95% da diferença entre duas proporções: `1,96 × raiz(p1(1−p1)/n1 + p2(1−p2)/n2)`. Só a diferença maior que a margem vira frase na página. Python aparece em 64,7% das vagas de entrada e em 86,9% das de pleno para cima: diferença de 22,2 pontos, margem de 18,2, então entra. Estatística aparece mais nas de entrada (41,2% contra 23,0%), mas a diferença de 18,2 fica dentro da margem de 19,6, então não vira achado. Não é um teste formal, mas evita vender ruído como resultado. Com grupos de 34 e 61 vagas, a margem passa de 15 pontos na maioria das skills.

## 10. O que esses números NÃO permitem afirmar? O que você faria a seguir?

Não permitem falar do mercado brasileiro: são 31 empresas que usam três plataformas, a maioria fintechs e empresas de tecnologia, e sem a Gupy. Também não dizem se a skill é exigida ou só desejável, porque o dicionário só registra a menção. E nível e área vêm do título, que é uma aproximação. A seguir, eu: (1) deixaria a coleta semanal rodar algumas semanas para ver a evolução, que hoje tem uma semana só; (2) separaria "obrigatório" de "desejável" pela seção da descrição em que a skill aparece; (3) procuraria uma fonte com mais vagas júnior que permita coleta.
