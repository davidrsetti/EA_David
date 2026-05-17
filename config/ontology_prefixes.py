"""
config/ontology_prefixes.py — Prefix registry aligned to v10 ontology
(ea-ontology-consolidated-10.ttl).

The prefix labels and base URIs match the live Stardog export. Backwards-compatible
aliases (e.g. `nexus` for `ops`, `agent` for `ai`) point to the same namespace
URIs so older SPARQL in sparql_corrections.py and tests continues to resolve.
"""
EA_BASE    = "https://ontology.ea.example.org/"
OPS_BASE   = "https://nexus.platform/"
EAAI_BASE  = "urn:EA_AI_Intelligence:"

PREFIXES: dict[str, str] = {
    # ── W3C / common ──────────────────────────────────────────────────
    "rdf":     "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs":    "http://www.w3.org/2000/01/rdf-schema#",
    "owl":     "http://www.w3.org/2002/07/owl#",
    "xsd":     "http://www.w3.org/2001/XMLSchema#",
    "skos":    "http://www.w3.org/2004/02/skos/core#",
    "sh":      "http://www.w3.org/ns/shacl#",
    "so":      "https://schema.org/",

    # ── v10 domain namespaces (22 total — exact URIs from live Stardog) ─
    "ea":      f"{EA_BASE}ea#",
    "hr":      f"{EA_BASE}hr#",
    "id":      f"{EA_BASE}identity#",
    "app":     f"{EA_BASE}app#",
    "sol":     f"{EA_BASE}solution#",
    "intg":    f"{EA_BASE}integration#",
    "infra":   f"{EA_BASE}infra#",
    "net":     f"{EA_BASE}network#",
    "fw":      f"{EA_BASE}firewall#",
    "cost":    f"{EA_BASE}cost#",
    "sec":     f"{EA_BASE}security#",
    "ai":      f"{EA_BASE}ai#",
    "adv":     f"{EA_BASE}advisor#",
    "art":     f"{EA_BASE}artifact#",
    "gov":     f"{EA_BASE}gov#",
    "data":    f"{EA_BASE}data#",
    "ekg":     f"{EA_BASE}ekg#",
    "arch":    f"{EA_BASE}arch#",
    "gskref":  f"{EA_BASE}gsk-ref#",
    "ops":     f"{OPS_BASE}ops#",
    "EAAI":    EAAI_BASE,

    # ── Backwards-compatible aliases (same URI, different prefix label) ─
    # `nexus` is used in sparql_corrections.py + tests for the ops# namespace.
    "nexus":   f"{OPS_BASE}ops#",
    # `agent` was the pre-migration label for ai# (CLAUDE.md migration table).
    "agent":   f"{EA_BASE}ai#",
    # `org` and `iam` retained as legacy aliases mapping to hr/identity.
    "org":     f"{EA_BASE}hr#",
    "iam":     f"{EA_BASE}identity#",
}

SPARQL_PREFIX_BLOCK: str = "\n".join(f"PREFIX {k}: <{v}>" for k, v in PREFIXES.items())

# Lifecycle states recognised by the apm_agent / sa_advisor modules.
# Sourced from app:lifecycle rdfs:comment in the v10 TTL.
LIFECYCLE_STATUSES = [
    "active", "maintain", "sunset", "legacy",
    "retire", "eol", "development", "pilot",
]

# Risk tiers recognised on ai:Agent (ai:riskTier).
RISK_TIERS = ["Low", "Medium", "High", "Critical"]

# DOMAIN_HINTS — guidance injected into the NL→SPARQL / clarifier prompts.
# Each value lists the most useful classes & predicates for that domain so the
# LLM picks the right vocabulary. Keep terse — these are reminders, not docs.
DOMAIN_HINTS: dict[str, str] = {
    "people":         "hr:User · hr:Manager · hr:employeeId · hr:memberOfDepartment · hr:hasMember · <urn:EA_AI_Intelligence:manages_user>",
    "organisation":   "hr:Organization · hr:Department · hr:costCentre · hr:hasDepartment · hr:belongsToOrganization",
    "identity":       "id:Identity · id:DigitalUser · id:Group · id:ServicePrincipal · id:Role · id:Permission · id:Certification · id:linkedUser · id:assignedRole · id:grantsPermission",
    "applications":   "app:Application · app:SaaSApplication · app:CustomApplication · app:PlatformService · app:vendor · app:lifecycle · app:hostingEnv · app:techOwner · app:ownedByDepartment · app:dependsOn · ea:enablesBusinessCapability",
    "solutions":      "sol:Solution · sol:SolutionComponent · sol:Disposition · sol:usesApplication · sol:usesTechnology · sol:addressesCapability · sol:categorizedAs · sol:ownedBy",
    "capabilities":   "ea:BusinessCapabilityL1/L2/L3 · ea:TechnologyCapabilityL1/L2/L3 · ea:CSOCapabilityL1/L2/L3 · ea:hasBusinessCapabilityL1/L2/L3 · app:hasCapability · ea:enablesBusinessCapability",
    "architecture":   "ea:EADomain · ea:EABusinessDomain · ea:EATechnologyDomain · ea:EASecurityDomain · ea:EASolutionDomain · ea:TechArchetype · ea:TechPattern · ea:BusinessArchetype · ea:SolutionCategory · ea:Platform · ea:Technology",
    "integration":    "intg:Integration · intg:IntegrationPattern · intg:DataEntity · intg:sourceApplication · intg:targetApplication · intg:transfersDataEntity · intg:usesIntegrationPattern",
    "infrastructure": "infra:Infrastructure · infra:Compute · infra:Storage · infra:LoadBalancer · infra:ContainerCluster · infra:hostsApplication · infra:hostsTechnology · infra:supportsPlatform",
    "network":        "net:Network · net:VirtualNetwork · net:Subnet · net:PrivateEndpoint · net:DNSZone · net:addressSpace · net:containsSubnet",
    "firewall":       "fw:FirewallPolicy · fw:FirewallRule · fw:appliesToNetwork · fw:permitsIntegration · fw:port · fw:protocol · fw:action",
    "cost":           "cost:CostModel · cost:LicenceCost · cost:InfraEstimate · cost:BuildCost · cost:annualAmount · cost:currency · cost:relatedToSolution · cost:relatedToTechnology · cost:licenceForApplication",
    "security":       "sec:SecurityPolicy · sec:DataClassification · sec:SecurityControl · sec:RiskAssessment · sec:TrustLevel · sec:governsApplication · sec:classifiesDataEntity · sec:grantsAccessTo · sec:hasAccess",
    "agents":         "ai:Agent · ai:LLM · ai:Task · ai:Result · ai:AgentTool · ai:AgentPolicy · ai:AISkill · ai:poweredBy · ai:governedByPolicy · ai:hasSkill · ai:hasTool · ai:ownedBy · ai:scopedTo · ai:riskTier",
    "ai_skills":      "ai:AISkill · ai:skillType (Generative|Analytical|Reasoning|Vision) · ai:skillMaturity (Experimental|Emerging|Established|Mature) · ai:modelFamily · ai:hasSkill · ai:skillImplementedBy · ai:skillEnabledByPlatform",
    "advisor":        "adv:ArchitectureRequirement · adv:ArchitectureOption · adv:ArchitectureDecision · adv:ArchitecturalRule · adv:ArchitecturalPrinciple · adv:RoadmapItem · adv:DuplicateRisk · adv:hasOption · adv:decidedForRequirement",
    "artifacts":      "art:EAArtifact · art:ConceptualDiagram · art:LogicalDiagram · art:IntegrationDiagram · art:NetworkDiagram · art:ArchitectureDiagram · art:diagramType · art:documentsSolution",
    "governance":     "gov:Vendor · gov:Contract · gov:SLA · gov:ChangeRequest · gov:PolicyException · gov:AuditEvent · gov:Regulation · gov:BusinessTerm · gov:DataPolicy · gov:DataQualityRule · gov:regulatedBy · gov:governedBy",
    "data":           "data:Dataset · data:DataDomain · data:DataProduct · data:DataPipeline · data:DataStore · data:VectorStore · data:FeatureStore · data:MLModel · data:LineageRecord · data:containsPII · data:steward · data:dataOwner · data:lineageFrom",
    "ekg_meta":       "ekg:KnowledgeGraphMeta · ekg:KnowledgeStore · ekg:NamedGraph · ekg:OntologyModule · ekg:databaseName",
    "reference_arch": "arch:ReferenceArchitecture · arch:ArchitectureLayer · arch:ArchitectureComponent · arch:hasLayer · arch:hasComponent · arch:usesTechnology · gskref:GSK_AIAgent_AccessMgmt_Ref",
    "findings":       "ops:AgentFinding · ops:severity · ops:findingStatus · ops:foundBy · ops:affects · ops:reviewedBy · (alias: nexus:AgentFinding)",
    "sessions":       "ops:ConversationSession · ops:sessionUserId · ops:sessionUserRole · ops:turnCount · ops:startedAt · ops:lastActive · ops:entityFocus",
}
