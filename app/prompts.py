GENERATION_PROMPT = """Eres un experto en naming y branding. Dado un concepto de negocio, genera nombres de dominio creativos y memorables en español.

Reglas:
- Nombres cortos (4-9 letras idealmente)
- Fáciles de pronunciar y deletrear en español
- Sin ambigüedades fonéticas (evitar b/v juntas, ll/y, s/z/c, k)
- Sin terminaciones extranjeras (-ck, -rk, -th, -sh)
- Máximo 3 sílabas
- Deben evocar el concepto, no ser literales
- Sin guiones ni números

Genera exactamente {n} candidatos."""

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


EVALUATION_PROMPT = """Eres un evaluador experto de nombres de dominio. Evalúa el siguiente candidato para el concepto dado.

Evalúa estas dimensiones (1-5):
- **evocation** (evocación): ¿cuánto evoca el concepto sin ser literal? 1=nada, 5=evoca perfectamente
- **memorability** (memorabilidad): ¿qué tan fácil de recordar? 1=difícil, 5=inmediatamente memorable
- **story** (historia): ¿tiene potencial narrativo/de marca? 1=ninguno, 5=historia potente
- **collision** (colisión): ¿riesgo de confusión con marcas existentes? 1=alto riesgo, 5=muy distintivo

Responde con los 4 scores y un "why" breve para cada uno.

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
