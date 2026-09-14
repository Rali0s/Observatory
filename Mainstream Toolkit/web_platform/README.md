# Observatory web application

Keep this Django application inside `Mainstream Toolkit`: it imports analysis and publishing engines from the parent directory.

Use the maintained repository guides:

- [Project overview](../../README.md)
- [Installation: macOS, Linux, Windows, PostgreSQL](../../INSTALL.md)
- [Secrets and API credentials](../../SECURITY.md)
- [Source archives](../../ARCHIVING.md)
- [Railway deployment](../docs/RAILWAY_DEPLOYMENT.md)

On macOS/Linux, run `make setup`, `make run`, and `make worker` from the repository root. Configuration is loaded from this directory's `.env`; environment variables take precedence. Do not commit `.env`, the parent `.env.stripe`, databases, or credentials.

The app includes private writing tools, password/Xverse authentication, public reading/profiles, invitations, account merging, and optional payment/ordinal integrations. Payment and trading switches default off. Earlier milestone documents are historical records, not current installation instructions.
