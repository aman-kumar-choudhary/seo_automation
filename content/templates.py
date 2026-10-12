"""Content templates for platform-specific SEO variations."""
from __future__ import annotations

# Platform specific templates ensuring natural keyword usage, varied tone, and exact target URL
PLATFORM_TEMPLATES = {
    "technical": {
        "title_templates": [
            "Technical Overview: {keyword} Architecture and IoT Integration | Innovions",
            "Implementing Scalable {keyword} Tracking in Modern Infrastructure — Innovions",
            "Hardware & Protocols: Understanding Industrial {keyword} Systems with Innovions",
        ],
        "description_templates": [
            "An engineering perspective on {keyword} integration, signal processing, and enterprise hardware systems. Discover implementation patterns, telemetry workflows, and practical architecture at {target_url}.",
            "Deep-dive into industrial {keyword} technology and sensor deployment for connected operations. Innovions provides practical design considerations and deployment insights. Explore details at {target_url}.",
        ],
        "tags": "RFID, IoT, hardware-engineering, asset-tracking, industrial-tech",
    },
    "enterprise": {
        "title_templates": [
            "Enterprise Asset Tracking: Modernizing Operations with {keyword} | Innovions",
            "Supply Chain Visibility: The Strategic Impact of {keyword} Systems — Innovions",
            "Optimizing Inventory Logistics with Enterprise {keyword} Technology | Innovions",
        ],
        "description_templates": [
            "Transforming enterprise logistics through automated {keyword} identification, warehouse visibility, and real-time inventory management. Innovions offers practical insights for business operations. Learn more at {target_url}.",
            "Discover how next-generation {keyword} infrastructure reduces operational friction and improves auditability across complex supply networks. Read the full overview from Innovions at {target_url}.",
        ],
        "tags": "RFID, supply-chain, enterprise-software, logistics, asset-management",
    },
    "community": {
        "title_templates": [
            "Discussion: Real-World {keyword} Deployment Challenges & Innovations | Innovions",
            "Exploring High-Accuracy {keyword} Solutions in Industrial IoT — Innovions",
            "Practical Guide to Modern {keyword} Technology and Implementation | Innovions",
        ],
        "description_templates": [
            "A comprehensive overview examining practical considerations for {keyword} tagging, reader antennas, and workflow automation. Connect with Innovions to explore industry use cases: {target_url}.",
            "Sharing key learnings on deploying reliable {keyword} tracking solutions for inventory control and physical asset monitoring. Review the documentation and resources at {target_url}.",
        ],
        "tags": "RFID, technology, industrial-automation, smart-hardware",
    },
    "general": {
        "title_templates": [
            "Innovions: Advanced {keyword} Technology and Business Applications",
            "Smart Asset Management with Next-Generation {keyword} Solutions | Innovions",
            "Innovions Resource: Complete Guide to Commercial {keyword} Systems",
        ],
        "description_templates": [
            "Explore Innovions' perspective on {keyword} technology and practical business applications. Featuring reliable identification systems and implementation roadmaps. Learn more at {target_url}.",
            "A curated resource covering cutting-edge {keyword} devices, middleware, and practical tracking integrations designed by Innovions. Visit {target_url} for full details.",
        ],
        "tags": "RFID, business, technology, innovation",
    },
}

PLATFORM_STYLE_MAP = {
    "dev.to": "technical",
    "news.ycombinator.com": "technical",
    "github.com": "technical",
    "linkedin.com": "enterprise",
    "bizsugar.com": "enterprise",
    "reddit.com": "community",
    "slashdot.org": "community",
    "diigo.com": "general",
    "folkd.com": "general",
    "medium.com": "general",
}


def get_template_style(platform_name: str, domain: str = "") -> str:
    domain_clean = domain.strip().lower().removeprefix("www.")
    if domain_clean in PLATFORM_STYLE_MAP:
        return PLATFORM_STYLE_MAP[domain_clean]
    name_clean = platform_name.strip().lower()
    for d, style in PLATFORM_STYLE_MAP.items():
        if d.split(".")[0] in name_clean:
            return style
    return "general"
