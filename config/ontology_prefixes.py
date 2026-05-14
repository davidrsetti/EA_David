
"""
config/ontology_prefixes_v2.py — expanded prefix registry for NEXUS buildout.

Key additions:
- cmdb / itsm prefixes for ServiceNow and operational graph integration
- LIFECYCLE_STATUSES and RISK_TIERS constants used by advisor/APM code
- richer DOMAIN_HINTS for logical applications, instances, incidents, and changes
"""
BASE    = "http://example.com/"
NEXUS   = "http://nexus.enterprise.com/"

PREFIXES: dict[str, str] = {
    "rdf":    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs":   "http://www.w3.org/2000/01/rdf-schema#",
    "owl":    "http://www.w3.org/2002/07/owl#",
    "xsd":    "http://www.w3.org/2001/XMLSchema#",
    "skos":   "http://www.w3.org/2004/02/skos/core#",
    "sh":     "http://www.w3.org/ns/shacl#",

    # Core domain prefixes (base: http://example.com/)
    "ea":      f"{BASE}ea#",
    "hr":      f"{BASE}hr#",
    "org":     f"{BASE}org#",
    "app":     f"{BASE}app#",
    "sol":     f"{BASE}sol#",
    "prod":    f"{BASE}prod#",
    "arch":    f"{BASE}arch#",
    "intg":    f"{BASE}int#",
    "infra":   f"{BASE}infra#",
    "net":     f"{BASE}net#",
    "fw":      f"{BASE}fw#",
    "cost":    f"{BASE}cost#",
    "data":    f"{BASE}data#",
    "gov":     f"{BASE}gov#",
    "sec":     f"{BASE}sec#",
    "iam":     f"{BASE}iam#",
    "entra":   f"{BASE}entra#",
    "ai":      f"{BASE}ai#",
    "adv":     f"{BASE}advisor#",
    "art":     f"{BASE}artifact#",
    "kg":      f"{BASE}kg#",
    "doc":     f"{BASE}doc#",
    "ds":      f"{BASE}datasource#",
    "denodo":  f"{BASE}denodo#",
    "cmdb":    f"{BASE}cmdb#",
    "itsm":    f"{BASE}itsm#",

    # Platform prefixes (base: http://nexus.enterprise.com/)
    "nexus":   f"{NEXUS}ops#",
    "audit":   f"{NEXUS}audit#",
    "session": f"{NEXUS}session#",
    "agent":   f"{NEXUS}agent#",
}

SPARQL_PREFIX_BLOCK: str = "\n".join(f"PREFIX {k}: <{v}>" for k, v in PREFIXES.items())

LIFECYCLE_STATUSES = ["Development", "Pilot", "Active", "Maintain", "Sunset", "Legacy", "Retire", "EOL"]
RISK_TIERS = ["Low", "Medium", "High", "Critical"]

DOMAIN_HINTS: dict[str, str] = {
    "people":         "hr:User · hr:fullName · hr:mail · hr:employeeId · hr:belongsToDepartment · hr:managerOf",
    "organisation":   "hr:Department · ea:EATechnologyDomain · ea:EACSODomain",
    "applications":   "app:Application · app:techOwner · app:departmentOwner · app:businessOwner · app:uciid · app:environment · ea:enablesBusinessCapabilityL3",
    "architecture":   "ea:BusinessCapabilityL1/L2/L3 · ea:TechnologyCapabilityL1/L2/L3 · ea:CSOCapabilityL1/L2/L3 · ea:hasTechnologyCapabilityL1 · ea:hasCSOCapabilityL1",
    "capabilities":   "ea:BusinessCapabilityL3 · ea:enablesBusinessCapabilityL3 · ea:isEnabledByApplication · ea:hasChildBusinessCapability · ea:businessParentOf",
    "technology":     "ea:Technology · ea:technologyName · ea:enablesTechnologyCapabilityL3 · ea:technologyParentOf · ea:hasChildTechnologyCapability",
    "security":       "sec:SecurityPolicy · sec:AccessRight · sec:policyTags",
    "agents":         "ai:Agent · ai:name · ai:description · ai:ownedByUser",
    "sessions":       "session:ConversationSession · session:userId · session:userRole · session:status · session:turnCount · session:startedAt",
}
