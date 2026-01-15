# Admin UI Service

Next.js 14 administrative dashboard for the RAG Knowledge Indexing System.

## Features

- **Dashboard Overview**: Real-time system statistics and metrics
- **Knowledge Sources Management**: Add, configure, and manage data sources
- **API Token Management**: Create and revoke API tokens
- **Job Monitoring**: Track ingestion job status and progress
- **Search Playground**: Test semantic search with configurable parameters
- **Audit Logs**: View system activity and user actions
- **System Settings**: Configure global settings and preferences

## Technology Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Data Fetching**: React Query (TanStack Query)
- **HTTP Client**: Axios

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── (dashboard)/        # Protected dashboard routes
│   │   ├── dashboard/      # Dashboard overview
│   │   ├── sources/        # Knowledge sources management
│   │   ├── tokens/         # API token management
│   │   ├── jobs/           # Ingestion job monitoring
│   │   ├── search/         # Search playground
│   │   ├── audit/          # Audit logs
│   │   └── settings/       # System settings
│   ├── login/              # Login page
│   ├── layout.tsx          # Root layout
│   └── globals.css         # Global styles
├── components/
│   ├── layout/             # Layout components
│   │   └── sidebar.tsx     # Dashboard sidebar
│   ├── providers.tsx       # Context providers
│   └── ui/                 # Reusable UI components
│       ├── badge.tsx
│       ├── button.tsx
│       ├── card.tsx
│       ├── input.tsx
│       └── table.tsx
└── lib/
    ├── api.ts              # API client
    ├── store.ts            # Zustand store
    └── utils.ts            # Utility functions
```

## Environment Variables

| Variable                    | Description             | Default                 |
| --------------------------- | ----------------------- | ----------------------- |
| `NEXT_PUBLIC_API_URL`       | Management API base URL | `http://localhost:8001` |
| `NEXT_PUBLIC_QUERY_API_URL` | Query API base URL      | `http://localhost:8002` |

## Development

### Prerequisites

- Node.js 20+
- npm or yarn

### Running Locally

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at http://localhost:3000

### Using Docker

```bash
# Build development image
docker build -f Dockerfile.dev -t admin-ui:dev .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8001 \
  admin-ui:dev
```

## Production Build

```bash
# Build for production
npm run build

# Start production server
npm start
```

### Production Docker

```bash
# Build production image
docker build -t admin-ui:latest .

# Run container
docker run -p 3000:3000 admin-ui:latest
```

## Authentication

The Admin UI uses JWT-based authentication:

1. Users log in with email/password
2. Tokens are stored in localStorage
3. Access tokens are refreshed automatically
4. Protected routes redirect to login if unauthenticated

## User Roles

| Role          | Permissions                                      |
| ------------- | ------------------------------------------------ |
| `super_admin` | Full access to all features                      |
| `editor`      | Manage sources, tokens, view jobs and audit logs |
| `viewer`      | Read-only access to dashboard and logs           |

## API Integration

The UI communicates with two backend services:

### Management API (Port 8001)

- Authentication
- Source management
- Token management
- Job monitoring
- Audit logs
- System settings

### Query API (Port 8002)

- Search playground queries
- Multi-source search

## Pages

### Login (`/login`)

- Email/password authentication
- Redirect to dashboard on success

### Dashboard (`/dashboard`)

- Total documents count
- Active sources count
- Total chunks count
- Recent jobs summary
- System health indicators

### Sources (`/sources`)

- List all knowledge sources
- Add new source (Confluence, Slack, File Upload)
- Edit source configuration
- Trigger manual sync
- Delete sources

### API Tokens (`/tokens`)

- List all API tokens
- Create new tokens with scopes
- Set token expiration
- Revoke tokens
- Copy token to clipboard

### Jobs (`/jobs`)

- List ingestion jobs with status
- Filter by status, source
- View job progress
- View job logs and errors

### Search (`/search`)

- Interactive search playground
- Configure window size (0-3)
- Set number of results
- Test different queries
- View relevance scores

### Audit Logs (`/audit`)

- View all system actions
- Filter by entity type, action, user
- View detailed event data

### Settings (`/settings`)

- Chunk size configuration
- Embedding model selection
- Sync interval settings
- System preferences

## Styling

The UI uses Tailwind CSS with a custom color scheme:

- Primary: Indigo (#6366f1)
- Dark theme with semi-transparent cards
- Consistent spacing and typography

## Contributing

1. Follow the TypeScript style guide
2. Use functional components with hooks
3. Implement proper error handling
4. Add loading states for async operations
5. Use React Query for data fetching
