# Admin UI - Requirements & Features

## Overview
Modern, responsive web interface for administering the RAG knowledge system. Built with Next.js 14+ using App Router, TypeScript, and performance-optimized React patterns.

## Core Responsibilities
- User authentication and session management
- Source management interface
- Token generation and management
- Job monitoring and control
- Analytics dashboards
- System settings configuration
- Audit log viewing

## Technology Stack
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript 5.3+
- **UI Components**: Shadcn/ui (Radix UI + Tailwind)
- **Styling**: Tailwind CSS 3.4+
- **State Management**: React Context + Hooks (lightweight state)
- **Data Fetching**: React Server Components + SWR for client-side
- **Forms**: React Hook Form + Zod validation
- **Charts**: Recharts
- **Tables**: TanStack Table v8
- **HTTP Client**: Native fetch with custom wrapper

## Performance Requirements

### Core Web Vitals Targets
- **LCP (Largest Contentful Paint)**: <2.5s
- **FID (First Input Delay)**: <100ms
- **CLS (Cumulative Layout Shift)**: <0.1
- **TTI (Time to Interactive)**: <3.5s

### Optimization Strategies
- Server-side rendering for initial page load
- Code splitting by route
- Image optimization with Next.js Image component
- Lazy loading for heavy components
- Debounced search inputs
- Virtual scrolling for large lists
- Memoization of expensive computations

## Architecture

### Folder Structure
```
services/admin-ui/
├── public/
│   ├── icons/
│   └── images/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── layout.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx          # Main dashboard layout
│   │   │   ├── page.tsx            # Overview dashboard
│   │   │   ├── sources/
│   │   │   │   ├── page.tsx        # Sources list
│   │   │   │   ├── [id]/
│   │   │   │   │   ├── page.tsx    # Source detail
│   │   │   │   │   └── edit/page.tsx
│   │   │   │   └── new/page.tsx
│   │   │   ├── tokens/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── [id]/page.tsx
│   │   │   │   └── new/page.tsx
│   │   │   ├── jobs/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   ├── analytics/
│   │   │   │   └── page.tsx
│   │   │   ├── settings/
│   │   │   │   └── page.tsx
│   │   │   └── audit/
│   │   │       └── page.tsx
│   │   ├── api/                    # API route handlers
│   │   │   └── auth/
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                     # Shadcn/ui components
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   ├── sources/
│   │   │   ├── SourceCard.tsx
│   │   │   ├── SourceForm.tsx
│   │   │   ├── SourceStats.tsx
│   │   │   └── ConfluenceConfig.tsx
│   │   ├── tokens/
│   │   │   ├── TokenCard.tsx
│   │   │   ├── TokenForm.tsx
│   │   │   └── TokenDisplay.tsx
│   │   ├── jobs/
│   │   │   ├── JobList.tsx
│   │   │   ├── JobProgress.tsx
│   │   │   └── JobDetails.tsx
│   │   ├── analytics/
│   │   │   ├── OverviewCards.tsx
│   │   │   ├── UsageChart.tsx
│   │   │   └── QueryAnalytics.tsx
│   │   └── common/
│   │       ├── DataTable.tsx
│   │       ├── SearchInput.tsx
│   │       ├── Pagination.tsx
│   │       └── LoadingSpinner.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts           # API client wrapper
│   │   │   ├── sources.ts
│   │   │   ├── tokens.ts
│   │   │   ├── jobs.ts
│   │   │   └── analytics.ts
│   │   ├── auth/
│   │   │   ├── session.ts
│   │   │   └── middleware.ts
│   │   ├── utils/
│   │   │   ├── format.ts
│   │   │   ├── validation.ts
│   │   │   └── dates.ts
│   │   └── hooks/
│   │       ├── useAuth.ts
│   │       ├── useSources.ts
│   │       ├── useTokens.ts
│   │       └── useJobs.ts
│   ├── types/
│   │   ├── api.ts
│   │   ├── source.ts
│   │   ├── token.ts
│   │   └── job.ts
│   └── middleware.ts
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

## Pages & Features

### 1. Login Page
**Route**: `/login`

**Features**:
- Email/password authentication
- Remember me checkbox
- Password reset link
- Session management
- Error handling with user feedback

**Implementation**:
```typescript
// app/(auth)/login/page.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { apiClient } from '@/lib/api/client';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  rememberMe: z.boolean().optional(),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/api/v1/auth/login', {
        email: data.email,
        password: data.password,
      });

      // Store token
      localStorage.setItem('access_token', response.access_token);
      
      // Redirect to dashboard
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <h2 className="text-3xl font-bold text-center">Sign in</h2>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              {...register('email')}
              disabled={isLoading}
            />
            {errors.email && (
              <p className="text-sm text-red-600 mt-1">{errors.email.message}</p>
            )}
          </div>

          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              {...register('password')}
              disabled={isLoading}
            />
            {errors.password && (
              <p className="text-sm text-red-600 mt-1">{errors.password.message}</p>
            )}
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded">
              {error}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  );
}
```

### 2. Dashboard Overview
**Route**: `/`

**Features**:
- System statistics cards (sources, documents, tokens, queries)
- Recent activity timeline
- Quick actions (add source, create token)
- Active jobs status
- Usage graphs (last 7/30 days)

**Components**:
```typescript
// components/analytics/OverviewCards.tsx
interface StatsCard {
  title: string;
  value: number | string;
  change?: number;
  icon: React.ReactNode;
}

export function OverviewCards({ stats }: { stats: any }) {
  const cards: StatsCard[] = [
    {
      title: 'Total Sources',
      value: stats.total_sources,
      change: stats.sources_change_7d,
      icon: <Database className="h-4 w-4" />,
    },
    {
      title: 'Documents Indexed',
      value: stats.total_documents.toLocaleString(),
      change: stats.documents_change_7d,
      icon: <FileText className="h-4 w-4" />,
    },
    {
      title: 'Active Tokens',
      value: stats.active_tokens,
      icon: <Key className="h-4 w-4" />,
    },
    {
      title: 'Queries (7d)',
      value: stats.queries_7d.toLocaleString(),
      change: stats.queries_change,
      icon: <Search className="h-4 w-4" />,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              {card.title}
            </CardTitle>
            {card.icon}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{card.value}</div>
            {card.change !== undefined && (
              <p className={`text-xs ${card.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {card.change >= 0 ? '+' : ''}{card.change}% from last period
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

### 3. Sources Management
**Route**: `/sources`

**Features**:
- Grid/list view toggle
- Search and filter (by type, status)
- Source cards with quick stats
- Add new source button
- Bulk actions (sync, activate/deactivate)
- Sort options

**Source Detail Page** (`/sources/[id]`):
- Source information
- Configuration display
- Document list (paginated)
- Sync history
- Statistics graphs
- Edit/delete actions
- Manual sync trigger

**Add Source Form** (`/sources/new`):
- Multi-step wizard:
  1. Select source type
  2. Configure connection
  3. Test connection
  4. Configure chunking
  5. Set sync schedule
  6. Review and create
- Real-time validation
- Connection testing
- Help text and examples

```typescript
// components/sources/SourceForm.tsx
export function SourceForm() {
  const [step, setStep] = useState(1);
  const [sourceType, setSourceType] = useState<string>('');
  
  const steps = [
    { id: 1, name: 'Type', component: SelectSourceType },
    { id: 2, name: 'Configure', component: ConfigureSource },
    { id: 3, name: 'Test', component: TestConnection },
    { id: 4, name: 'Chunking', component: ConfigureChunking },
    { id: 5, name: 'Schedule', component: SetSchedule },
    { id: 6, name: 'Review', component: ReviewAndCreate },
  ];

  return (
    <div className="max-w-4xl mx-auto">
      <Stepper currentStep={step} steps={steps} />
      
      <div className="mt-8">
        {React.createElement(steps[step - 1].component, {
          sourceType,
          onNext: () => setStep(step + 1),
          onBack: () => setStep(step - 1),
        })}
      </div>
    </div>
  );
}

// components/sources/ConfigureChunking.tsx
export function ConfigureChunking({ 
  values, 
  onChange, 
  onNext, 
  onBack 
}: ChunkingConfigProps) {
  const { register, handleSubmit, watch, formState: { errors } } = useForm({
    defaultValues: {
      chunk_size_chars: 1000,
      respect_boundaries: true,
      min_chunk_size_chars: 200,
    },
  });

  const chunkSize = watch('chunk_size_chars');

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configure Chunking</CardTitle>
        <CardDescription>
          Define how documents should be split into chunks. No overlap is needed - 
          context is provided via sliding window at query time.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <Label htmlFor="chunk_size_chars">
            Chunk Size (characters)
          </Label>
          <Input
            id="chunk_size_chars"
            type="number"
            min={500}
            max={4000}
            step={100}
            {...register('chunk_size_chars', {
              min: { value: 500, message: 'Minimum 500 characters' },
              max: { value: 4000, message: 'Maximum 4000 characters' },
            })}
          />
          <p className="text-sm text-muted-foreground mt-1">
            Recommended: 800-1200 for chat, 1000-1500 for documentation
          </p>
          {errors.chunk_size_chars && (
            <p className="text-sm text-red-600 mt-1">
              {errors.chunk_size_chars.message}
            </p>
          )}
          
          {/* Preview */}
          <div className="mt-4 p-4 bg-muted rounded border">
            <p className="text-sm font-medium mb-2">Preview:</p>
            <p className="text-xs text-muted-foreground">
              With {chunkSize} characters per chunk, a typical document page 
              (~5000 chars) would be split into {Math.ceil(5000 / chunkSize)} chunks.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Checkbox
            id="respect_boundaries"
            {...register('respect_boundaries')}
          />
          <Label htmlFor="respect_boundaries" className="cursor-pointer">
            Respect natural boundaries (sentences, paragraphs)
          </Label>
        </div>
        <p className="text-sm text-muted-foreground">
          When enabled, chunks will try to break at sentence or paragraph 
          boundaries rather than mid-sentence. This improves semantic coherence.
        </p>

        <div>
          <Label htmlFor="min_chunk_size_chars">
            Minimum Chunk Size (characters)
          </Label>
          <Input
            id="min_chunk_size_chars"
            type="number"
            min={100}
            max={chunkSize}
            {...register('min_chunk_size_chars', {
              min: { value: 100, message: 'Minimum 100 characters' },
              max: { 
                value: chunkSize, 
                message: 'Must be less than chunk size' 
              },
            })}
          />
          <p className="text-sm text-muted-foreground mt-1">
            Chunks smaller than this will be discarded
          </p>
        </div>

        <Alert>
          <InfoIcon className="h-4 w-4" />
          <AlertTitle>About Chunking</AlertTitle>
          <AlertDescription>
            Documents are split into sequential chunks without overlap. 
            When querying, you can use a "sliding window" to retrieve 
            adjacent chunks for additional context. This approach is more 
            efficient than overlapping chunks during ingestion.
          </AlertDescription>
        </Alert>
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={handleSubmit(onNext)}>
          Continue
        </Button>
      </CardFooter>
    </Card>
  );
}
```
```

### 4. Token Management
**Route**: `/tokens`

**Features**:
- Token list with search
- Filter by type, status
- Usage statistics per token
- Create token button
- Revoke/rotate actions
- Copy token (only on creation)

**Token Creation** (`/tokens/new`):
- Form fields:
  - Name and description
  - Token type selection
  - Source scope selector (multi-select with search)
  - Rate limits (per minute/day)
  - Expiration date (optional)
- One-time token display
- Copy to clipboard with confirmation
- Security warning

```typescript
// components/tokens/TokenDisplay.tsx
'use client';

import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function TokenDisplay({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);

  const copyToken = async () => {
    await navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-2 text-yellow-900">
        ⚠️ Save this token securely
      </h3>
      <p className="text-sm text-yellow-800 mb-4">
        This token will only be shown once. Store it securely as you won't be able to see it again.
      </p>
      
      <div className="bg-white p-4 rounded border border-gray-300 font-mono text-sm break-all">
        {token}
      </div>
      
      <Button
        onClick={copyToken}
        className="mt-4"
        variant="outline"
      >
        {copied ? (
          <>
            <Check className="h-4 w-4 mr-2" />
            Copied!
          </>
        ) : (
          <>
            <Copy className="h-4 w-4 mr-2" />
            Copy to clipboard
          </>
        )}
      </Button>
    </div>
  );
}
```

### 5. Jobs Monitoring
**Route**: `/jobs`

**Features**:
- Real-time job list
- Status badges (pending, running, completed, failed)
- Progress bars for running jobs
- Filter by status, source, date range
- Cancel running jobs
- Retry failed jobs
- Job details modal

**Job Progress Component**:
```typescript
// components/jobs/JobProgress.tsx
'use client';

import { useEffect, useState } from 'react';
import { Progress } from '@/components/ui/progress';
import { apiClient } from '@/lib/api/client';

export function JobProgress({ jobId }: { jobId: string }) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('pending');

  useEffect(() => {
    const interval = setInterval(async () => {
      const job = await apiClient.get(`/api/v1/jobs/${jobId}`);
      
      setStatus(job.status);
      
      if (job.progress?.processed && job.progress?.total) {
        setProgress((job.progress.processed / job.progress.total) * 100);
      }
      
      if (['completed', 'failed', 'cancelled'].includes(job.status)) {
        clearInterval(interval);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [jobId]);

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="capitalize">{status}</span>
        <span>{Math.round(progress)}%</span>
      </div>
      <Progress value={progress} />
    </div>
  );
}
```

### 6. Analytics Dashboard
**Route**: `/analytics`

**Features**:
- Date range selector
- Query volume over time (line chart)
- Top queries table
- Per-source statistics
- Token usage breakdown
- Cache hit rate graph
- Average query latency
- Export reports (CSV/PDF)

**Charts Implementation**:
```typescript
// components/analytics/UsageChart.tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function UsageChart({ data }: { data: any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Query Volume</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line 
              type="monotone" 
              dataKey="queries" 
              stroke="#8884d8" 
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

### 7. System Settings
**Route**: `/settings`

**Features**:
- Tabs for different setting categories:
  - General (embedding model, chunking params)
  - Search (default top_k, min score)
  - Rate Limits (default limits)
  - Retention Policies
  - Integrations (API keys)
- Form validation
- Save confirmation
- Reset to defaults option

### 8. Audit Logs
**Route**: `/audit`

**Features**:
- Filterable table (user, action, resource, date)
- Export logs
- Detail modal for each entry
- Timeline view option
- Search functionality

## API Client Implementation

```typescript
// lib/api/client.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = localStorage.getItem('access_token');
    
    const headers = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Redirect to login
        window.location.href = '/login';
      }
      
      const error = await response.json();
      throw new Error(error.detail || 'API request failed');
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async patch<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new APIClient(API_BASE_URL);
```

## Data Fetching Strategy

### Server Components (Initial Load)
```typescript
// app/(dashboard)/sources/page.tsx
import { apiClient } from '@/lib/api/client';

async function getSources() {
  // Fetched on server, cached
  const response = await fetch(`${API_URL}/api/v1/sources`, {
    next: { revalidate: 60 }, // Revalidate every 60 seconds
  });
  return response.json();
}

export default async function SourcesPage() {
  const sources = await getSources();
  
  return <SourcesList initialData={sources} />;
}
```

### Client Components (Real-time Updates)
```typescript
// hooks/useSources.ts
import useSWR from 'swr';

export function useSources() {
  const { data, error, isLoading, mutate } = useSWR(
    '/api/v1/sources',
    (url) => apiClient.get(url),
    {
      refreshInterval: 30000, // Refresh every 30 seconds
      revalidateOnFocus: true,
    }
  );

  return {
    sources: data?.items || [],
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
```

## Form Validation

```typescript
// types/source.ts
import * as z from 'zod';

export const confluenceConfigSchema = z.object({
  base_url: z.string().url('Must be a valid URL'),
  space_keys: z.array(z.string()).min(1, 'At least one space required'),
  credentials: z.object({
    email: z.string().email(),
    api_token: z.string().min(1, 'API token required'),
  }),
  options: z.object({
    include_attachments: z.boolean().default(true),
    include_archived: z.boolean().default(false),
  }),
});

export const sourceSchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters'),
  description: z.string().optional(),
  type: z.enum(['confluence', 'slack', 'file_upload']),
  config: z.record(z.any()), // Validated based on type
  sync_frequency: z.string().regex(/^(@(yearly|monthly|weekly|daily|hourly)|(\d+|\*) (\d+|\*) (\d+|\*) (\d+|\*) (\d+|\*))$/),
});
```

## Responsive Design

### Breakpoints
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

### Mobile Optimizations
- Collapsible sidebar
- Simplified navigation
- Touch-friendly buttons
- Optimized table layouts (horizontal scroll or card view)

## Performance Optimizations

### Code Splitting
```typescript
// Lazy load heavy components
const AnalyticsDashboard = dynamic(
  () => import('@/components/analytics/AnalyticsDashboard'),
  { loading: () => <LoadingSpinner /> }
);
```

### Memoization
```typescript
// Expensive computations
const sortedSources = useMemo(
  () => sources.sort((a, b) => b.updated_at - a.updated_at),
  [sources]
);
```

### Virtual Scrolling
```typescript
// For large lists (1000+ items)
import { useVirtualizer } from '@tanstack/react-virtual';

export function VirtualSourceList({ sources }: { sources: Source[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  
  const virtualizer = useVirtualizer({
    count: sources.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100,
  });

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <SourceCard
            key={virtualItem.key}
            source={sources[virtualItem.index]}
          />
        ))}
      </div>
    </div>
  );
}
```

## Error Handling

```typescript
// components/common/ErrorBoundary.tsx
'use client';

import { Component, ReactNode } from 'react';

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2 className="text-2xl font-bold mb-4">Something went wrong</h2>
          <Button onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

## Testing

### Unit Tests (Jest + React Testing Library)
```typescript
// components/sources/__tests__/SourceCard.test.tsx
import { render, screen } from '@testing-library/react';
import { SourceCard } from '../SourceCard';

describe('SourceCard', () => {
  it('renders source information', () => {
    const source = {
      id: '123',
      name: 'Test Source',
      type: 'confluence',
      document_count: 100,
    };

    render(<SourceCard source={source} />);
    
    expect(screen.getByText('Test Source')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });
});
```

### E2E Tests (Playwright)
```typescript
// tests/e2e/login.spec.ts
import { test, expect } from '@playwright/test';

test('user can log in', async ({ page }) => {
  await page.goto('/login');
  
  await page.fill('input[name="email"]', 'admin@example.com');
  await page.fill('input[name="password"]', 'password123');
  await page.click('button[type="submit"]');
  
  await expect(page).toHaveURL('/');
  await expect(page.locator('h1')).toContainText('Dashboard');
});
```

## Configuration

### Environment Variables
```bash
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_APP_NAME=RAG Knowledge Admin
```

## Dependencies
```json
{
  "dependencies": {
    "next": "14.1.0",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-label": "^2.0.2",
    "@radix-ui/react-select": "^2.0.0",
    "@radix-ui/react-tabs": "^1.0.4",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "react-hook-form": "^7.49.3",
    "@hookform/resolvers": "^3.3.4",
    "zod": "^3.22.4",
    "swr": "^2.2.4",
    "recharts": "^2.10.4",
    "@tanstack/react-table": "^8.11.6",
    "@tanstack/react-virtual": "^3.0.1",
    "date-fns": "^3.2.0",
    "lucide-react": "^0.312.0",
    "tailwindcss": "^3.4.1",
    "tailwind-merge": "^2.2.0",
    "tailwindcss-animate": "^1.0.7"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "@types/node": "^20.11.5",
    "@types/react": "^18.2.48",
    "@testing-library/react": "^14.1.2",
    "@testing-library/jest-dom": "^6.2.0",
    "@playwright/test": "^1.41.1",
    "eslint": "^8.56.0",
    "eslint-config-next": "14.1.0"
  }
}
```
