GENERATION_PROMPT = """Dado un concepto de negocio, genera nombres de dominio creativos y memorables.

Reglas:
- Nombres cortos (4-9 letras), solo minúsculas sin tildes
- Fáciles de deletrear en español
- Evitar la letra K y terminaciones extranjeras (-ck, -rk, -th)
- Máximo 3 sílabas
- Sin TLD (.com, .net, etc.) en el nombre
- Sin guiones ni números
- Evocar el concepto, no ser literal

Responde solo este JSON, sin texto antes ni después:
{{"candidates": [{{"name": "ejemplo", "rationale": "por qué evoca el concepto"}}]}}

Genera {n} candidatos para: {concept}"""

GENERATION_SCHEMA = {
    "name": "domain_candidates",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Nombre de dominio candidato, solo letras minúsculas, sin TLD"
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Breve explicación de por qué este nombre encaja con el concepto"
                        }
                    },
                    "required": ["name", "rationale"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["candidates"],
        "additionalProperties": False
    }
}


EVALUATION_PROMPT = """Evalúa este nombre de dominio para el concepto dado. Responde ÚNICAMENTE con JSON, sin texto antes ni después.

Dimensiones (1-5):
- evocation: ¿cuánto evoca el concepto? (why: breve explicación)
- memorability: ¿qué tan fácil de recordar? (why: breve explicación)
- story: ¿potencial narrativo/de marca? (why: breve explicación)
- collision: ¿riesgo de confusión con marcas existentes? 5=muy distintivo (why: breve explicación)

Formato exacto:
{{"evocation": {{"value": 4, "why": "..."}}, "memorability": {{"value": 4, "why": "..."}}, "story": {{"value": 4, "why": "..."}}, "collision": {{"value": 4, "why": "..."}}}}

Candidato: {name}
Concepto: {concept}"""

EVALUATION_SCHEMA = {
    "name": "domain_evaluation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "evocation": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "minimum": 1, "maximum": 5},
                    "why": {"type": "string"}
                },
                "required": ["value", "why"],
                "additionalProperties": False
            },
            "memorability": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "minimum": 1, "maximum": 5},
                    "why": {"type": "string"}
                },
                "required": ["value", "why"],
                "additionalProperties": False
            },
            "story": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "minimum": 1, "maximum": 5},
                    "why": {"type": "string"}
                },
                "required": ["value", "why"],
                "additionalProperties": False
            },
            "collision": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "minimum": 1, "maximum": 5},
                    "why": {"type": "string"}
                },
                "required": ["value", "why"],
                "additionalProperties": False
            }
        },
        "required": ["evocation", "memorability", "story", "collision"],
        "additionalProperties": False
    }
}

TEST_CONCEPTS = [
    "quilara",
    "marketplace de artesanías mexicanas",
    "fintech de microcréditos para pymes",
]
