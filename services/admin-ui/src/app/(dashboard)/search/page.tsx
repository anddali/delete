"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

interface SearchResult {
  document_id: string;
  document_title: string;
  document_url?: string;
  source_name: string;
  source_type: string;
  similarity: number;
  extended_content: string;
  chunks: Array<{
    chunk_id: string;
    content: string;
    position: number;
    is_match: boolean;
  }>;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [slidingWindow, setSlidingWindow] = useState(1);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTime, setSearchTime] = useState<number | null>(null);

  const handleSearch = async () => {
    if (!query || !apiKey) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_QUERY_API_URL}/query/search`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": apiKey,
          },
          body: JSON.stringify({
            query,
            sliding_window: slidingWindow,
            limit: 10,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data = await response.json();
      setResults(data.results);
      setSearchTime(data.search_time_ms);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="mb-6 text-3xl font-bold">Search Test</h1>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Test Query API</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium">API Key</label>
              <Input
                type="password"
                placeholder="Enter API key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">Query</label>
              <Input
                placeholder="Enter search query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Sliding Window (0-3)
              </label>
              <div className="flex gap-2">
                {[0, 1, 2, 3].map((n) => (
                  <Button
                    key={n}
                    variant={slidingWindow === n ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSlidingWindow(n)}
                  >
                    {n}
                  </Button>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Number of adjacent chunks to include for context
              </p>
            </div>

            <Button
              onClick={handleSearch}
              disabled={loading || !query || !apiKey}
            >
              <Search className="mr-2 h-4 w-4" />
              {loading ? "Searching..." : "Search"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      {searchTime !== null && (
        <p className="mb-4 text-sm text-muted-foreground">
          Found {results.length} results in {searchTime.toFixed(2)}ms
        </p>
      )}

      <div className="space-y-4">
        {results.map((result, index) => (
          <Card key={index}>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">
                    {result.document_title}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {result.source_name} ({result.source_type})
                  </p>
                </div>
                <Badge variant="secondary">
                  {(result.similarity * 100).toFixed(1)}% match
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {result.document_url && (
                <a
                  href={result.document_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mb-2 block text-sm text-blue-600 hover:underline"
                >
                  {result.document_url}
                </a>
              )}

              <div className="mt-4 rounded-lg bg-gray-50 p-4">
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  Extended Content ({result.chunks.length} chunks)
                </p>
                <div className="text-sm">
                  {result.chunks.map((chunk, i) => (
                    <span
                      key={i}
                      className={chunk.is_match ? "bg-yellow-100" : ""}
                    >
                      {chunk.content}
                      {i < result.chunks.length - 1 && " "}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
