from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Initialize model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Canonical token map: maps each category to representative phrases
canonical_intents = {
    "GET_RUNNING_RESOURCES": [
        "get all running resources",
        "show running resources",
        "list all active services",
        "what resources are currently running?",
        "fetch all running instances",
        "get currently running systems",
        "display all running VMs",
        "running services list",
        "which resources are active?"
    ],
    "GET_STOPPED_RESOURCES": [
        "get all stopped resources",
        "show stopped resources",
        "list all inactive services",
        "what resources are currently stopped?",
        "fetch all stopped instances",
        "get currently halted systems",
        "display stopped VMs",
        "stopped services list",
        "which resources are not running?"
    ],
    "START_STOPPED_RESOURCES": [
        "start all stopped resources",
        "start all inactive resources",
        "boot up all stopped services",
        "power on all halted instances",
        "resume all stopped machines",
        "bring up everything that is currently stopped",
        "start all VMs that aren’t running",
        "activate all idle resources",
        "restart all stopped nodes"
    ],
    "STOP_RUNNING_RESOURCES": [
        "stop all resources",
        "stop all running resources",
        "stop all active services",
        "shut down all running resources",
        "power off all running instances",
        "halt all active machines",
        "shut everything down",
        "turn off all VMs",
        "deactivate currently running resources",
        "kill all running tasks"
    ],
    "TENANT_DETAILS": [
        # Direct Requests
        "get tenant details",
        "fetch tenant info",
        "retrieve tenant metadata",
        "show tenant information",
        "list all tenants",
        "pull tenant records",
        "display tenant details",
        "fetch all tenants",
        "return tenant list",

        # Specific Data Types
        "get tenant names",
        "list tenant IDs",
        "fetch tenant account names",
        "retrieve tenant configurations",
        "show all tenant attributes",

        # Descriptive Questions
        "what tenants are available?",
        "which tenants are active?",
        "do we have any tenants configured?",
        "what are the tenant names?",
        "who are the tenants?",
        "how many tenants exist?",

        # Command-like Variants
        "show me the tenants",
        "list the tenants now",
        "give me tenant details",
        "output tenant info",

        # Context-Aware Queries
        "fetch tenants for this account",
        "list tenants for environment X",
        "get tenants created recently",
        "find tenant with name 'xyz'"
    ]
}

# Flattened version: maps example -> token
flat_examples = {}
for token, examples in canonical_intents.items():
    for example in examples:
        flat_examples[example] = token

# Tokenizer function
def Get_token(sentence: str, threshold=0.9) -> str:
    flat_examples = {}
    for token, examples in canonical_intents.items():
        for example in examples:
            flat_examples[example] = token

    input_vec = model.encode([sentence])[0]
    for canon_sentence, token in flat_examples.items():
        canon_vec = model.encode([canon_sentence])[0]
        sim = cosine_similarity([input_vec], [canon_vec])[0][0]
        if sim >= threshold:
            return token
    return "UNKNOWN_INTENT"

# Example usage
if __name__ == "__main__":
    test_sentences = [
        "fetch all active services",
        "turn off all VMs",
        "boot all halted resources",
        "what's running?",
        "show all systems",
    ]

    for s in test_sentences:
        tok = get_token(s, flat_examples)
        print(f"'{s}' => {tok}")
