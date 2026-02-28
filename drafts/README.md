# Draft Research Ideas

Place your preliminary research ideas here as YAML files. Each file is a self-contained
project draft that the engine reads as input.

## Usage

```bash
fct-engine pipeline -i drafts/my_project.yaml
fct-engine generate -i drafts/my_project.yaml -o output/
```

## File format

See `example_idea.yaml` for a complete example. Minimum required fields:

```yaml
title: "Your Project Title"
research_topic: "1-3 paragraphs describing the research idea."
```

All other fields are optional — the engine fills them from config.yaml defaults
or generates them using AI.

## Files

| File | Description |
|------|-------------|
| example_idea.yaml | Complete DigiResilient example (SR&TD, 36mo, €200k) |
| pdspp_pilot_pex.yaml | PDSPP-Pilot synthetic health data portal (PEX, 18mo, €56k) |
| pdspp_pilot_pex_complete.yaml | PDSPP-Pilot with placeholder fields for update |
| ehds_sandbox_pex_complete.yaml | EHDS Sandbox governance pilot (PEX, 18mo, €57k) |
| synthpoppt_icdt_complete.yaml | SynthPopPT population engine (SR&TD, 36mo, €240k) |
| vbhc_synthpt_icdt_complete.yaml | VBHC-SynthPT value-based modelling (SR&TD, 36mo, €238k) |
