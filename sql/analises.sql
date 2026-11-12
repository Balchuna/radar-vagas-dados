-- Análises do Radar de Vagas (SQLite).
--
-- Cada bloco começa com "-- nome: <identificador>". O bloco "_preparar" cria visões
-- temporárias (somem ao fechar a conexão; o banco não é alterado). Os demais blocos são
-- consultas que o script scripts/relatorio.py executa, imprime e grava em
-- docs/dados/agregados.json e docs/index.html.
--
-- Recortes usados:
--   "ativas"      = vagas que apareceram na última coleta de cada empresa (ativa = 1);
--   "dados"       = área inferida pelo título = 'dados';
--   "acessivel"   = nível no título é estágio, júnior ou não informado. Quase nenhuma vaga
--                   destas fontes diz "júnior"; as sem nível são as que, em tese, aceitam
--                   quem está começando. É uma hipótese, não uma garantia.
--   "pleno_ou_acima" = pleno, sênior ou liderança.

-- nome: _preparar
CREATE TEMP VIEW IF NOT EXISTS v_ativas AS
SELECT v.*,
       e.nome AS empresa,
       f.nome AS fonte,
       CASE WHEN v.senioridade IN ('estagio', 'junior', 'nao_informada') THEN 'acessivel'
            ELSE 'pleno_ou_acima' END AS grupo_nivel
FROM vagas v
JOIN empresas e ON e.id = v.empresa_id
JOIN fontes f ON f.id = v.fonte_id
WHERE v.ativa = 1;

CREATE TEMP VIEW IF NOT EXISTS v_dados AS
SELECT * FROM v_ativas WHERE area = 'dados';

CREATE TEMP VIEW IF NOT EXISTS v_dados_skill AS
SELECT d.id AS vaga_id, d.grupo_nivel, s.nome AS skill, s.categoria
FROM v_dados d
JOIN vaga_skill vs ON vs.vaga_id = d.id
JOIN skills s ON s.id = vs.skill_id;

-- nome: panorama
-- Uma linha com a data da coleta e os totais que aparecem no topo do relatório.
SELECT
    (SELECT MAX(ultima_vez_vista) FROM vagas)                                        AS ultima_coleta,
    (SELECT MIN(primeira_vez_vista) FROM vagas)                                      AS primeira_coleta,
    (SELECT COUNT(DISTINCT execucao) FROM coletas)                                   AS execucoes,
    (SELECT COUNT(DISTINCT date(execucao)) FROM coletas)                             AS dias_com_coleta,
    (SELECT COUNT(*) FROM coletas
      WHERE execucao = (SELECT MAX(execucao) FROM coletas))                          AS empresas_consultadas,
    (SELECT COUNT(*) FROM coletas
      WHERE execucao = (SELECT MAX(execucao) FROM coletas) AND status = 'ok')        AS empresas_ok,
    (SELECT COUNT(DISTINCT empresa_id) FROM v_ativas)                                AS empresas_com_vaga,
    (SELECT COUNT(*) FROM v_ativas)                                                  AS vagas_ativas,
    (SELECT COUNT(*) FROM v_ativas WHERE area = 'ti')                                AS vagas_ti,
    (SELECT COUNT(*) FROM v_dados)                                                   AS vagas_dados,
    (SELECT COUNT(*) FROM v_dados WHERE grupo_nivel = 'acessivel')                   AS vagas_dados_acessiveis,
    (SELECT COUNT(*) FROM v_dados WHERE senioridade IN ('estagio', 'junior'))        AS vagas_dados_junior_estagio,
    (SELECT COUNT(*) FROM v_ativas
      WHERE area IN ('dados', 'ti') AND senioridade IN ('estagio', 'junior'))        AS vagas_dados_ti_junior_estagio,
    (SELECT MIN(publicada_em) FROM v_ativas)                                         AS publicacao_mais_antiga,
    (SELECT MAX(publicada_em) FROM v_ativas)                                         AS publicacao_mais_recente,
    (SELECT MAX(versao_skills) FROM coletas)                                         AS versao_dicionario_skills;

-- nome: area_por_nivel
-- Vagas ativas por área e nível inferido pelo título.
SELECT area,
       SUM(senioridade = 'estagio')       AS estagio,
       SUM(senioridade = 'junior')        AS junior,
       SUM(senioridade = 'pleno')         AS pleno,
       SUM(senioridade = 'senior')        AS senior,
       SUM(senioridade = 'lideranca')     AS lideranca,
       SUM(senioridade = 'nao_informada') AS nao_informada,
       COUNT(*)                           AS total
FROM v_ativas
GROUP BY area
ORDER BY CASE area WHEN 'dados' THEN 1 WHEN 'ti' THEN 2 ELSE 3 END;

-- nome: top_skills_dados
-- Skills mais pedidas nas vagas de dados (todos os níveis). pct = % das vagas de dados.
SELECT skill,
       categoria,
       COUNT(*)                                                       AS vagas,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1)    AS pct
FROM v_dados_skill
GROUP BY skill, categoria
ORDER BY vagas DESC, skill
LIMIT 20;

-- nome: top_skills_dados_acessiveis
-- O mesmo, só nas vagas de dados de estágio, júnior ou sem nível no título.
SELECT skill,
       categoria,
       COUNT(*)                                                                         AS vagas,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados WHERE grupo_nivel = 'acessivel'), 1) AS pct
FROM v_dados_skill
WHERE grupo_nivel = 'acessivel'
GROUP BY skill, categoria
ORDER BY vagas DESC, skill
LIMIT 15;

-- nome: skills_por_nivel_dados
-- Compara o recorte acessível com pleno ou acima, para as skills que aparecem em pelo
-- menos 10 vagas de dados (abaixo disso, a comparação é só ruído). Cada pct é sobre o
-- total de vagas de dados do próprio grupo. Ordem: skills mais típicas do recorte
-- acessível primeiro. O relatório acrescenta a margem de erro de cada diferença.
WITH total AS (
    SELECT SUM(grupo_nivel = 'acessivel') AS n_acessivel,
           SUM(grupo_nivel = 'pleno_ou_acima') AS n_pleno
    FROM v_dados
),
por_skill AS (
    SELECT skill,
           COUNT(*)                               AS vagas_dados,
           SUM(grupo_nivel = 'acessivel')         AS vagas_acessiveis,
           SUM(grupo_nivel = 'pleno_ou_acima')    AS vagas_pleno_ou_acima
    FROM v_dados_skill
    GROUP BY skill
    HAVING COUNT(*) >= 10
)
SELECT p.skill,
       p.vagas_dados,
       p.vagas_acessiveis,
       t.n_acessivel                                                     AS total_acessiveis,
       ROUND(100.0 * p.vagas_acessiveis / t.n_acessivel, 1)              AS pct_acessiveis,
       p.vagas_pleno_ou_acima,
       t.n_pleno                                                         AS total_pleno_ou_acima,
       ROUND(100.0 * p.vagas_pleno_ou_acima / t.n_pleno, 1)              AS pct_pleno_ou_acima,
       ROUND(100.0 * p.vagas_acessiveis / t.n_acessivel
             - 100.0 * p.vagas_pleno_ou_acima / t.n_pleno, 1)            AS diferenca_pp
FROM por_skill p
CROSS JOIN total t
ORDER BY diferenca_pp DESC, p.skill;

-- nome: categorias_dados
-- % das vagas de dados que pedem pelo menos uma skill de cada categoria do dicionário.
SELECT categoria,
       COUNT(DISTINCT vaga_id)                                                   AS vagas,
       ROUND(100.0 * COUNT(DISTINCT vaga_id) / (SELECT COUNT(*) FROM v_dados), 1) AS pct
FROM v_dados_skill
GROUP BY categoria
ORDER BY vagas DESC, categoria;

-- nome: pares_skills_dados
-- Pares de skills que aparecem juntos na mesma vaga de dados.
SELECT a.skill                                                      AS skill_1,
       b.skill                                                      AS skill_2,
       COUNT(*)                                                     AS vagas,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1)  AS pct
FROM v_dados_skill a
JOIN v_dados_skill b ON b.vaga_id = a.vaga_id AND a.skill < b.skill
GROUP BY a.skill, b.skill
ORDER BY vagas DESC, skill_1, skill_2
LIMIT 15;

-- nome: modalidade
-- Remoto, híbrido e presencial. pct_do_recorte conta as vagas sem informação;
-- pct_das_informadas desconsidera essas vagas.
WITH base AS (
    SELECT 'dados' AS recorte, modalidade FROM v_dados
    UNION ALL
    SELECT 'dados_e_ti', modalidade FROM v_ativas WHERE area IN ('dados', 'ti')
    UNION ALL
    SELECT 'todas', modalidade FROM v_ativas
),
contagem AS (
    SELECT recorte, modalidade, COUNT(*) AS vagas FROM base GROUP BY recorte, modalidade
)
SELECT recorte,
       modalidade,
       vagas,
       ROUND(100.0 * vagas / SUM(vagas) OVER (PARTITION BY recorte), 1) AS pct_do_recorte,
       CASE WHEN modalidade = 'nao_informada' THEN NULL
            ELSE ROUND(100.0 * vagas / SUM(CASE WHEN modalidade <> 'nao_informada' THEN vagas END)
                                       OVER (PARTITION BY recorte), 1)
       END AS pct_das_informadas
FROM contagem
ORDER BY CASE recorte WHEN 'dados' THEN 1 WHEN 'dados_e_ti' THEN 2 ELSE 3 END,
         CASE modalidade WHEN 'remoto' THEN 1 WHEN 'hibrido' THEN 2 WHEN 'presencial' THEN 3 ELSE 4 END;

-- nome: ferramentas_bi
-- Power BI x Looker x Tableau (e as outras ferramentas de BI do dicionário) nas vagas de dados.
WITH ferramenta(skill) AS (
    VALUES ('Power BI'), ('Looker'), ('Tableau'), ('Qlik'), ('Metabase'), ('Excel/planilhas')
)
SELECT f.skill,
       COUNT(ds.vaga_id)                                                     AS vagas,
       ROUND(100.0 * COUNT(ds.vaga_id) / (SELECT COUNT(*) FROM v_dados), 1)  AS pct,
       COALESCE(SUM(ds.grupo_nivel = 'acessivel'), 0)                        AS vagas_acessiveis
FROM ferramenta f
LEFT JOIN v_dados_skill ds ON ds.skill = f.skill
GROUP BY f.skill
ORDER BY vagas DESC, f.skill;

-- nome: bi_combinacoes
-- Quantas vagas de dados pedem só uma das três ferramentas, mais de uma ou nenhuma.
WITH marcas AS (
    SELECT d.id,
           COALESCE(MAX(ds.skill = 'Power BI'), 0) AS power_bi,
           COALESCE(MAX(ds.skill = 'Looker'), 0)   AS looker,
           COALESCE(MAX(ds.skill = 'Tableau'), 0)  AS tableau
    FROM v_dados d
    LEFT JOIN v_dados_skill ds ON ds.vaga_id = d.id
    GROUP BY d.id
),
grupos AS (
    SELECT CASE
             WHEN power_bi + looker + tableau = 0 THEN 'nenhuma das três'
             WHEN power_bi + looker + tableau > 1 THEN 'duas ou mais'
             WHEN power_bi = 1 THEN 'só Power BI'
             WHEN looker = 1 THEN 'só Looker'
             ELSE 'só Tableau'
           END AS combinacao
    FROM marcas
)
SELECT combinacao,
       COUNT(*)                                                    AS vagas,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1) AS pct
FROM grupos
GROUP BY combinacao
ORDER BY CASE combinacao WHEN 'só Power BI' THEN 1 WHEN 'só Looker' THEN 2 WHEN 'só Tableau' THEN 3
                         WHEN 'duas ou mais' THEN 4 ELSE 5 END;

-- nome: evolucao_semanal
-- Uma linha por semana com coleta (semana = segunda-feira, em UTC).
--   vistas: vagas que estavam no ar em alguma coleta da semana;
--   novas: vistas pela primeira vez na semana (na primeira semana, é todo o estoque);
--   encerradas: vagas que deixaram de aparecer e cuja última aparição foi na semana.
WITH semanas AS (
    SELECT DISTINCT date(execucao, 'weekday 0', '-6 days') AS semana FROM coletas
),
vagas_semana AS (
    SELECT id, area, ativa,
           date(primeira_vez_vista, 'weekday 0', '-6 days') AS semana_primeira,
           date(ultima_vez_vista, 'weekday 0', '-6 days')   AS semana_ultima
    FROM vagas
)
SELECT s.semana,
       SUM(v.area = 'dados' AND v.semana_primeira <= s.semana AND v.semana_ultima >= s.semana) AS dados_vistas,
       SUM(v.area = 'dados' AND v.semana_primeira = s.semana)                                AS dados_novas,
       SUM(v.area = 'dados' AND v.ativa = 0 AND v.semana_ultima = s.semana)                  AS dados_encerradas,
       SUM(v.semana_primeira <= s.semana AND v.semana_ultima >= s.semana)                    AS todas_vistas,
       SUM(v.semana_primeira = s.semana)                                                     AS todas_novas,
       SUM(v.ativa = 0 AND v.semana_ultima = s.semana)                                       AS todas_encerradas
FROM semanas s
CROSS JOIN vagas_semana v
GROUP BY s.semana
ORDER BY s.semana;

-- nome: idade_vagas_dados
-- Há quanto tempo as vagas de dados abertas foram publicadas, contando até a última coleta.
WITH idade AS (
    SELECT CASE
             WHEN publicada_em IS NULL THEN NULL
             ELSE julianday(date((SELECT MAX(ultima_vez_vista) FROM vagas))) - julianday(publicada_em)
           END AS dias
    FROM v_dados
)
SELECT CASE
         WHEN dias IS NULL THEN 'sem data'
         WHEN dias <= 7 THEN 'até 7 dias'
         WHEN dias <= 30 THEN '8 a 30 dias'
         WHEN dias <= 90 THEN '31 a 90 dias'
         ELSE 'mais de 90 dias'
       END AS faixa,
       COUNT(*)                                                    AS vagas,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1) AS pct
FROM idade
GROUP BY faixa
ORDER BY CASE faixa WHEN 'até 7 dias' THEN 1 WHEN '8 a 30 dias' THEN 2 WHEN '31 a 90 dias' THEN 3
                    WHEN 'mais de 90 dias' THEN 4 ELSE 5 END;

-- nome: empresas_dados
-- Empresas que mais publicam vagas de dados (entre as acompanhadas).
SELECT empresa,
       fonte,
       SUM(area = 'dados')                              AS vagas_dados,
       SUM(area = 'dados' AND grupo_nivel = 'acessivel') AS dados_acessiveis,
       SUM(area = 'ti')                                 AS vagas_ti,
       COUNT(*)                                         AS vagas_total
FROM v_ativas
GROUP BY empresa_id, empresa, fonte
HAVING SUM(area = 'dados') > 0
ORDER BY vagas_dados DESC, empresa
LIMIT 15;

-- nome: vagas_entrada
-- Vagas de dados e TI que dizem estágio ou júnior no título (lista completa).
SELECT area, senioridade, empresa, titulo, modalidade, publicada_em, url
FROM v_ativas
WHERE area IN ('dados', 'ti') AND senioridade IN ('estagio', 'junior')
ORDER BY area, senioridade, empresa, titulo;

-- nome: qualidade
-- Pontos fracos da classificação, para ler os números com cuidado.
SELECT 'vagas de dados sem nenhuma skill reconhecida' AS indicador,
       COUNT(*) AS vagas,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1) AS pct
FROM v_dados WHERE id NOT IN (SELECT vaga_id FROM vaga_skill)
UNION ALL
SELECT 'vagas de dados sem nível no título', COUNT(*),
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1)
FROM v_dados WHERE senioridade = 'nao_informada'
UNION ALL
SELECT 'vagas de dados com modalidade lida na descrição', COUNT(*),
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1)
FROM v_dados WHERE modalidade_origem = 'descricao'
UNION ALL
SELECT 'vagas de dados sem modalidade', COUNT(*),
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_dados), 1)
FROM v_dados WHERE modalidade = 'nao_informada';
