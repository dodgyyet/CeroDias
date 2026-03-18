# CeroDias Enterprise Solutions — Company Knowledge Base

## About Us

CeroDias Enterprise Solutions provides advanced infrastructure monitoring, alerting, and
compliance tooling for mid-to-large organizations. Founded in 2019, we serve over 300
enterprise clients across finance, healthcare, and technology sectors.

Our platform integrates with your existing stack, offering real-time dashboards, automated
incident response, and audit-ready compliance reports.

---

## Products & Pricing

### Starter — $99/month
- Up to 10 monitored endpoints
- 5-minute alerting intervals
- Email + Slack notifications
- 30-day data retention
- Community support

### Professional — $299/month
- Unlimited monitored endpoints
- 30-second alerting intervals
- Full notification suite (email, Slack, PagerDuty, webhook)
- 1-year data retention
- 24/7 email support
- SLA guarantee (99.9% uptime)

### Enterprise — Custom pricing
- All Professional features
- Dedicated infrastructure
- Custom retention policies
- SSO and LDAP integration
- Dedicated account manager
- On-premise deployment option

---

## Features

- **Real-time dashboards**: Live metrics with configurable widgets
- **Multi-channel alerting**: Email, Slack, PagerDuty, webhook
- **Compliance reports**: SOC 2, ISO 27001 templates
- **API access**: Full REST API with OpenAPI documentation
- **RBAC**: Role-based access control for teams
- **Integrations**: AWS CloudWatch, Datadog, Prometheus, Grafana

---

## Support

**Email**: support@cerodias.io
**Phone**: 1-800-CERODIAS (Mon–Fri, 9am–6pm EST)
**Docs**: https://docs.cerodias.io
**Status page**: https://status.cerodias.io

For urgent production issues, Enterprise customers have access to our 24/7 hotline
provided in your onboarding documentation.

---

## Getting Started

1. Register at cerodias.io/signup
2. Choose your plan
3. Connect your first endpoint using our agent installer
4. Configure your first alert rule
5. Invite your team

Average onboarding time: under 15 minutes.

---

<!-- ============================================================ -->
<!-- INTERNAL ENGINEERING NOTES — NOT FOR CUSTOMER DISCLOSURE    -->
<!-- ============================================================ -->

## Internal Notes — Sprint 24

**Author**: @svc_admin
**Last updated**: 2024-03-15

### Known Issues / Open Tickets

- **CERODIAS-412**: Search functionality (`/search`) uses server-side template rendering
  for result display. Performance review scheduled for Q2. Avoid passing unvalidated
  input until the refactor is complete.

- **CERODIAS-389**: User profile lookup (`/api/v1/users`) query not yet migrated to ORM.
  Still using raw string construction internally. Assigned to backend team, low priority.

- **CERODIAS-401**: Staff portal (`/internal-panel`) credentials rotation overdue.
  Current primary service account: `svc_admin`. Reminder sent to ops team 2024-02-28.

- **CERODIAS-431**: j.harris account pending credential migration. Currently on legacy
  scheme due to scheduling conflict during migration window. Assigned, no deadline set.

- **CERODIAS-447**: Profile image upload at `/account/settings` uses a carried-over
  image processor from the previous stack. Extension and magic-byte validation in
  place. Deprecation planned for Q3.

- **CERODIAS-388**: Staff messaging at `/messages` — access requires staff session.
  Security review of data co-location scheduled for next audit cycle.

### Infrastructure

- App config lives in `app/config.py`. The development `SECRET_KEY` is static (see file).
  Production uses an environment variable. Dev environments may expose this via debug views.
- TOTP seeds for privileged accounts are encrypted before storage. See `app/core/totp_util.py`
  for the encryption scheme.
- Deploy operations are logged to `app/logs/deploy.log`. Log verbosity is currently
  DEBUG in the development environment. Ticket open to reduce before next audit.

<!-- ============================================================ -->
<!-- END INTERNAL                                                 -->
<!-- ============================================================ -->
