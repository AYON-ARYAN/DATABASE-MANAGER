# Literature Review and References — *Meridian Data*

*An AI-powered natural-language-to-SQL database explorer with safety guardrails,
RBAC, AI data analysis, and automated dashboards.*

---

## 1. Literature Review

### 1.1 From Natural Language Interfaces to the Relational Model

The relational model introduced by Codd [1] established the table-based foundation on
which the Structured Query Language (SQL) and virtually all modern relational database
management systems (SQLite, PostgreSQL, MySQL, etc.) are built. While SQL is expressive
and precise, it imposes a steep learning curve on non-technical users, which is precisely
the barrier that Natural Language Interfaces to Databases (NLIDBs) have sought to remove
for several decades. The seminal survey by Androutsopoulos, Ritchie and Thanisch [2]
catalogued the early history of NLIDBs — from pattern-matching and syntax-based systems to
semantic-grammar and intermediate-representation architectures — and articulated the
trade-offs (portability, linguistic coverage, and user trust) that still shape the field
today. Early systems were brittle and database-specific; the central modern goal,
formalised by the Spider benchmark [5], is *cross-domain generalisation* — answering
questions over database schemas never seen during training. *Meridian Data* inherits this
ambition directly: it is schema-agnostic and connects to arbitrary databases at runtime,
introspecting their schemas rather than being trained on any single one.

### 1.2 Neural Text-to-SQL: Benchmarks and Architectures

The deep-learning era of text-to-SQL was catalysed by two datasets. Zhong, Xiong and
Socher introduced WikiSQL together with Seq2SQL [3], applying reinforcement learning so
that execution results — rather than only token-level loss — could supervise the generation
of order-invariant query clauses. Xu, Liu and Song's SQLNet [4] then showed that a
sketch-based, sequence-to-set formulation with column attention could outperform Seq2SQL
*without* reinforcement learning by exploiting SQL's inherent structure. Both, however,
were limited to single-table SELECT queries. Yu et al.'s Spider [5] reset the bar with
10,181 questions over 200 multi-domain, multi-table databases and a strict
database-disjoint train/test split, exposing how poorly prior models generalised. The
architectural responses — RAT-SQL [6], with relation-aware self-attention unifying schema
encoding and schema linking, and BRIDGE [7], which interleaves question tokens with schema
and *cell values* in a single BERT-encoded sequence — directly addressed schema linking and
value grounding, two problems *Meridian Data* must also solve when binding a user's phrasing
to concrete tables and columns. PICARD [8] contributed an orthogonal and highly practical
idea: constraining an autoregressive decoder through incremental parsing so that
syntactically invalid SQL tokens are rejected at generation time — a guardrail philosophy
that *Meridian Data* echoes in its post-generation validation layer. Comprehensive surveys
by Katsogiannis-Meimarakis and Koutrika [9] provide the taxonomy that situates these systems.

### 1.3 Large Language Models for SQL Generation

The arrival of capable LLMs shifted the dominant paradigm from task-specific fine-tuning to
*in-context learning*. Rajkumar, Li and Bahdanau [10] established that a general-purpose
code LLM (Codex) is a remarkably strong zero-/few-shot baseline on Spider, and analysed its
characteristic failure modes. Pourreza and Rafiei's DIN-SQL [11] showed that decomposing
the problem into schema linking, classification, generation, and self-correction sub-tasks
raises few-shot accuracy by roughly ten points, while Gao et al.'s DAIL-SQL [12]
systematically dissected prompt engineering — question representation, example selection,
and example organisation — and topped the Spider leaderboard while explicitly optimising for
token efficiency. The community also recognised that Spider's schema-only setting understates
real-world difficulty: Li et al.'s BIRD benchmark [13] introduced large, "dirty" databases
requiring external knowledge and query-efficiency awareness, where even GPT-4 reached only
~55% execution accuracy versus ~93% for humans — a sobering reminder that *human oversight*
remains essential. The survey by Hong et al. [14] consolidates this LLM-based generation of
NLIDBs. *Meridian Data* operationalises exactly these findings: it uses an instruction-tuned
open model (Llama 3.3 70B [15]) with schema-aware prompting, served either by Groq's
deterministic Tensor Streaming Processor / LPU architecture [16] for low-latency inference or
by a local Ollama runtime for privacy-sensitive deployments.

### 1.4 Safety, Validation, and Access Control

Because a generated query executes against a live database, correctness alone is
insufficient — the system must be *safe*. The classic taxonomy of SQL-injection attacks and
countermeasures by Halfond, Viegas and Orso [17] frames the threat model and motivates
defensive parsing, parameterisation, and query whitelisting. *Meridian Data* combines
PICARD-style structural validation [8] with this security perspective, parsing each
generated statement to reject destructive or out-of-scope operations before execution.
Authorisation is layered on top via Role-Based Access Control, whose reference models were
formalised by Sandhu et al. [18]; roles constrain which schemas, tables, and operations a
given user (or the LLM acting on their behalf) may touch — the standard mechanism for
least-privilege enforcement in multi-user data systems. Finally, because LLM outputs are
probabilistic, *Meridian Data* keeps a human in the loop: the survey by Wu et al. [19]
on human-in-the-loop machine learning underpins the design choice to surface the generated
SQL for inspection, confirmation, and correction before any write or expensive read,
mitigating exactly the value-grounding and external-knowledge gaps exposed by BIRD [13].

### 1.5 Automated Analysis, Visualization, and Positioning

Beyond returning rows, *Meridian Data* performs AI-assisted data analysis and generates
dashboards automatically. This connects it to the literature on automated visualization:
Dibia and Demiralp's Data2Vis [20] treats visualization design as a neural
sequence-to-sequence translation from data to declarative (Vega-Lite) specifications, while
Narechania, Srinivasan and Stasko's NL4DV toolkit [21] maps natural-language queries to
analytic tasks and recommended chart specifications. *Meridian Data* unifies threads that
prior work largely pursued in isolation: it pairs LLM-based, schema-aware text-to-SQL
generation [11], [12], [14] with PICARD-style validation [8], RBAC-based authorisation [18],
SQL-injection-aware safety [17], explicit human oversight [19], and NL-driven automated
visualization [20], [21] in a single multi-database explorer. Its distinguishing
contribution is therefore not a new parsing algorithm but a *systems integration*: it takes
academically validated components — cross-domain generalisation [5], in-context decomposition
[11], constrained decoding [8], and access control [18] — and assembles them into a
deployable, guardrailed, privacy-flexible (cloud LPU [16] or local [15]) tool aimed at the
real-world, "dirty-database" conditions that BIRD [13] showed remain unsolved.

---

## 2. Summary of Selected Papers

| Authors (Year) [Ref] | Objectives | Strengths & Weaknesses | Tool / Technique Used | Limitations |
|---|---|---|---|---|
| Zhong, Xiong & Socher (2017) [3] | Translate NL questions to SQL over Wikipedia tables; release WikiSQL | **S:** First large-scale dataset (80k); RL using execution reward handles order-invariant clauses. **W:** Only single-table, single-SELECT queries | Augmented pointer network + policy-gradient reinforcement learning (Seq2SQL) | No joins, nesting, or aggregation across tables; single schema style |
| Xu, Liu & Song (2017) [4] | Generate SQL on WikiSQL without RL by exploiting SQL structure | **S:** Sketch + sequence-to-set avoids the "order matters" problem; beats Seq2SQL by 9–13% without RL. **W:** Sketch is hand-designed for WikiSQL's narrow grammar | Sketch-based slot filling + column attention (SQLNet) | Tied to WikiSQL's simple query template; no multi-table generalisation |
| Yu et al. (2018) [5] | Define a complex, cross-domain text-to-SQL task and benchmark (Spider) | **S:** 200 multi-table DBs, DB-disjoint split forces generalisation; now the de-facto benchmark. **W:** Schema-only (few/no cell values), so understates real-data difficulty | Human-labeled dataset + component-match / exact-set-match evaluation | Best 2018 model only 12.4% exact match; clean curated schemas unlike production DBs |
| Wang et al. (2020) [6] | Jointly solve schema encoding and schema linking for cross-DB parsing | **S:** Relation-aware self-attention unifies columns, tables, and their mentions; +8.7% on Spider. **W:** Heavy, fine-tuning-dependent; complex to train | Relation-aware Transformer encoder + grammar-based decoder (RAT-SQL); BERT augmentation | Requires task-specific training; no LLM zero-shot capability; compute-intensive |
| Scholak, Schucher & Bahdanau (2021) [8] | Stop fine-tuned LMs from emitting invalid SQL | **S:** Incremental parsing rejects inadmissible tokens at decode time; turns passable T5 into SOTA on Spider/CoSQL. **W:** Needs a fast incremental grammar checker in the loop | Constrained autoregressive decoding via incremental parsing (PICARD) | Guarantees syntactic/schema validity, not semantic correctness; adds decoding latency |
| Pourreza & Rafiei (2023) [11] | Improve LLM text-to-SQL via task decomposition and self-correction | **S:** Decomposition (schema-link → classify → generate → self-correct) adds ~10% few-shot; no fine-tuning. **W:** Long multi-call prompts are token-costly and slower | In-context learning with prompt decomposition + self-correction (DIN-SQL, GPT-4) | Cost/latency of multiple LLM calls; prompt-engineering effort; brittle to schema scale |
| Gao et al. (2023) [12] | Systematically benchmark prompt engineering for LLM text-to-SQL | **S:** Rigorous study of question representation, example selection/organisation; 86.6% on Spider with strong token efficiency. **W:** Gains tied to GPT-4-class models | Prompt-engineering framework + few-shot example selection (DAIL-SQL) | Depends on a very capable LLM; evaluated mainly on Spider, not dirty real-world DBs |
| Li et al. (2023) [13] | Benchmark text-to-SQL on large, real, "dirty" databases (BIRD) | **S:** 95 large DBs, 33 GB, external-knowledge + efficiency challenges; realistic. **W:** Very hard — exposes a wide model-vs-human gap | Database-grounded benchmark + execution & valid-efficiency-score metrics | GPT-4 only ~55% vs ~93% human; confirms human oversight still required |

---

## 3. References (IEEE style)

[1] E. F. Codd, "A relational model of data for large shared data banks," *Communications of the ACM*, vol. 13, no. 6, pp. 377–387, Jun. 1970, doi: 10.1145/362384.362685.

[2] I. Androutsopoulos, G. D. Ritchie, and P. Thanisch, "Natural language interfaces to databases — an introduction," *Natural Language Engineering*, vol. 1, no. 1, pp. 29–81, Mar. 1995, doi: 10.1017/S135132490000005X.

[3] V. Zhong, C. Xiong, and R. Socher, "Seq2SQL: Generating structured queries from natural language using reinforcement learning," *arXiv preprint* arXiv:1709.00103, 2017.

[4] X. Xu, C. Liu, and D. Song, "SQLNet: Generating structured queries from natural language without reinforcement learning," *arXiv preprint* arXiv:1711.04436, 2017.

[5] T. Yu, R. Zhang, K. Yang, M. Yasunaga, D. Wang, Z. Li, J. Ma, I. Li, Q. Yao, S. Roman, Z. Zhang, and D. Radev, "Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task," in *Proc. 2018 Conf. Empirical Methods in Natural Language Processing (EMNLP)*, Brussels, Belgium, 2018, pp. 3911–3921, doi: 10.18653/v1/D18-1425.

[6] B. Wang, R. Shin, X. Liu, O. Polozov, and M. Richardson, "RAT-SQL: Relation-aware schema encoding and linking for text-to-SQL parsers," in *Proc. 58th Annu. Meeting of the Association for Computational Linguistics (ACL)*, 2020, pp. 7567–7578, doi: 10.18653/v1/2020.acl-main.677.

[7] X. V. Lin, R. Socher, and C. Xiong, "Bridging textual and tabular data for cross-domain text-to-SQL semantic parsing," in *Findings of the Association for Computational Linguistics: EMNLP 2020*, 2020, pp. 4870–4888, doi: 10.18653/v1/2020.findings-emnlp.438.

[8] T. Scholak, N. Schucher, and D. Bahdanau, "PICARD: Parsing incrementally for constrained auto-regressive decoding from language models," in *Proc. 2021 Conf. Empirical Methods in Natural Language Processing (EMNLP)*, 2021, pp. 9895–9901, doi: 10.18653/v1/2021.emnlp-main.779.

[9] G. Katsogiannis-Meimarakis and G. Koutrika, "A survey on deep learning approaches for text-to-SQL," *The VLDB Journal*, vol. 32, no. 4, pp. 905–936, 2023, doi: 10.1007/s00778-022-00776-8.

[10] N. Rajkumar, R. Li, and D. Bahdanau, "Evaluating the text-to-SQL capabilities of large language models," *arXiv preprint* arXiv:2204.00498, 2022.

[11] M. Pourreza and D. Rafiei, "DIN-SQL: Decomposed in-context learning of text-to-SQL with self-correction," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 36, 2023, pp. 36339–36348.

[12] D. Gao, H. Wang, Y. Li, X. Sun, Y. Qian, B. Ding, and J. Zhou, "Text-to-SQL empowered by large language models: A benchmark evaluation," *Proc. VLDB Endowment*, vol. 17, no. 5, pp. 1132–1145, 2024, doi: 10.14778/3641204.3641221.

[13] J. Li, B. Hui, G. Qu, J. Yang, B. Li, B. Li, B. Wang, B. Qin, R. Geng, N. Huo, X. Zhou, C. Ma, G. Li, K. C. C. Chang, F. Huang, R. Cheng, and Y. Li, "Can LLM already serve as a database interface? A BIg bench for large-scale database grounded text-to-SQLs (BIRD)," in *Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track*, vol. 36, 2023.

[14] Z. Hong, Z. Yuan, Q. Zhang, H. Chen, J. Dong, F. Huang, and X. Huang, "Next-generation database interfaces: A survey of LLM-based text-to-SQL," *arXiv preprint* arXiv:2406.08426, 2024.

[15] A. Grattafiori, A. Dubey, A. Jauhri, A. Pandey, *et al.* (Llama Team, AI @ Meta), "The Llama 3 herd of models," *arXiv preprint* arXiv:2407.21783, 2024.

[16] D. Abts, J. Ross, J. Sparling, M. Wong-VanHaren, M. Baker, T. Hawkins, A. Bell, J. Thompson, T. Kahsai, G. Kimmell, J. Hwang, R. Leslie-Hurd, M. Bye, E. R. Creswick, M. Boyd, M. Venigalla, E. Laforge, J. Purdy, P. Kamath, D. Maheshwari, M. Beidler, G. Rosseel, O. Ahmad, G. Gagarin, R. Czekalski, A. Rane, S. Parmar, J. Werner, J. Sproch, A. Macias, and B. Kurtz, "Think fast: A tensor streaming processor (TSP) for accelerating deep learning workloads," in *Proc. ACM/IEEE 47th Annu. Int. Symp. Computer Architecture (ISCA)*, 2020, pp. 145–158, doi: 10.1109/ISCA45697.2020.00023.

[17] W. G. J. Halfond, J. Viegas, and A. Orso, "A classification of SQL-injection attacks and countermeasures," in *Proc. IEEE Int. Symp. Secure Software Engineering (ISSSE)*, Arlington, VA, USA, 2006.

[18] R. S. Sandhu, E. J. Coyne, H. L. Feinstein, and C. E. Youman, "Role-based access control models," *Computer*, vol. 29, no. 2, pp. 38–47, Feb. 1996, doi: 10.1109/2.485845.

[19] X. Wu, L. Xiao, Y. Sun, J. Zhang, T. Ma, and L. He, "A survey of human-in-the-loop for machine learning," *Future Generation Computer Systems*, vol. 135, pp. 364–381, 2022, doi: 10.1016/j.future.2022.05.014.

[20] V. Dibia and Ç. Demiralp, "Data2Vis: Automatic generation of data visualizations using sequence-to-sequence recurrent neural networks," *IEEE Computer Graphics and Applications*, vol. 39, no. 5, pp. 33–46, 2019, doi: 10.1109/MCG.2019.2924636.

[21] A. Narechania, A. Srinivasan, and J. Stasko, "NL4DV: A toolkit for generating analytic specifications for data visualization from natural language queries," *IEEE Transactions on Visualization and Computer Graphics*, vol. 27, no. 2, pp. 369–379, Feb. 2021, doi: 10.1109/TVCG.2020.3030378.
