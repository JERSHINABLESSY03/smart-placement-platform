# GitHub Checkpoint

## Repository name

Recommended: `smart-placement-platform`

## Branch strategy

- `main`: stable, verified releases and deployment-ready code.
- `develop`: integration branch for completed work.
- Feature and fix branches should start from `develop` and merge back through pull requests.
- Promote verified releases from `develop` to `main`.

## Commit convention

Use concise Conventional Commit messages with an appropriate type and imperative summary, for example:

- `feat: add timed assessment review`
- `fix: validate resume uploads`
- `docs: update deployment instructions`
- `test: cover analytics privacy`
- `chore: establish project baseline`

## Recommended GitHub repository description

`A Django platform for student placement preparation with aptitude and coding practice, timed assessments, private performance analytics, and an AI tutor.`

## Recommended README sections

1. Project overview
2. Features and current limitations
3. Architecture and technology stack
4. Prerequisites
5. Local setup and environment configuration
6. Database migrations and seed data
7. Running the development server
8. Running tests and Django checks
9. Docker Compose setup
10. Production deployment
11. Security and privacy notes
12. Contribution and branch workflow
13. License

## Next steps for connecting to GitHub

1. Create a GitHub repository named `smart-placement-platform`; do not initialize it with a README, license, or `.gitignore` because this local project already has its baseline commit.
2. Create the `develop` branch locally from `main`.
3. Add the new repository as the `origin` remote using its HTTPS or SSH URL.
4. Confirm the remote URL and inspect the outgoing commit list.
5. Push `main` and `develop` only when explicitly ready; no remote or push is configured by this checkpoint.
6. Configure branch protection and pull-request checks for `main`.
