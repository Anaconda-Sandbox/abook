# notebooks/

MCP-driven demo notebooks. Each is built and run **live** over the `runt`
nteract MCP (`mcp__runt__*` tools) by an agent inside Claude Code — not handed
to a headless executor. Each notebook ends with a **Data sources** section
citing the real eval data behind every claim (Constitution I).

- `gepa_demo.ipynb` — evolves the **system-prompt** harness slice (GEPA, kernel-resident state).
- `skillopt_demo.ipynb` — evolves the **skill-document** harness slice (SkillOpt, on-disk state).
