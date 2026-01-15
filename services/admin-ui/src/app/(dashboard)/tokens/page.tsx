"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tokensApi, sourcesApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { Plus, Trash2, Copy, Check, Key, Database } from "lucide-react";

interface TokenCreateData {
  name: string;
  source_ids?: string[];
  expires_in_days?: number;
  rate_limit?: number;
}

export default function TokensPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [newTokenName, setNewTokenName] = useState("");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [expiresInDays, setExpiresInDays] = useState<string>("");
  const [rateLimit, setRateLimit] = useState<string>("100");
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const queryClient = useQueryClient();

  const { data: tokens, isLoading } = useQuery({
    queryKey: ["tokens"],
    queryFn: tokensApi.list,
  });

  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: sourcesApi.list,
  });

  const createMutation = useMutation({
    mutationFn: (data: TokenCreateData) => tokensApi.create(data),
    onSuccess: (data) => {
      setCreatedToken(data.token);
      setNewTokenName("");
      setSelectedSources([]);
      setExpiresInDays("");
      setRateLimit("100");
      setShowCreate(false);
      queryClient.invalidateQueries({ queryKey: ["tokens"] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: tokensApi.revoke,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tokens"] });
    },
  });

  const copyToken = () => {
    if (createdToken) {
      navigator.clipboard.writeText(createdToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSourceToggle = (sourceId: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceId)
        ? prev.filter((id) => id !== sourceId)
        : [...prev, sourceId]
    );
  };

  const handleCreate = () => {
    const data: TokenCreateData = {
      name: newTokenName,
      rate_limit: parseInt(rateLimit) || 100,
    };
    
    if (selectedSources.length > 0) {
      data.source_ids = selectedSources;
    }
    
    if (expiresInDays && parseInt(expiresInDays) > 0) {
      data.expires_in_days = parseInt(expiresInDays);
    }
    
    createMutation.mutate(data);
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">API Tokens</h1>
          <p className="text-muted-foreground">Manage API tokens for query access</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Token
        </Button>
      </div>

      {/* Create Token Form */}
      {showCreate && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Create New API Token
            </CardTitle>
            <CardDescription>
              Tokens are used to authenticate API requests. You can scope tokens to specific sources.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Token Name */}
            <div className="space-y-2">
              <Label htmlFor="token-name">Token Name *</Label>
              <Input
                id="token-name"
                placeholder="e.g., Production API, Mobile App"
                value={newTokenName}
                onChange={(e) => setNewTokenName(e.target.value)}
              />
            </div>

            {/* Source Scoping */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2">
                <Database className="h-4 w-4" />
                Source Access
              </Label>
              <p className="text-sm text-muted-foreground">
                Select which sources this token can query. Leave empty to allow access to all sources.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-48 overflow-y-auto p-2 border rounded-md">
                {sources?.map((source: any) => (
                  <div
                    key={source.id}
                    className="flex items-center space-x-2 p-2 rounded hover:bg-muted"
                  >
                    <Checkbox
                      id={`source-${source.id}`}
                      checked={selectedSources.includes(source.id)}
                      onCheckedChange={() => handleSourceToggle(source.id)}
                    />
                    <label
                      htmlFor={`source-${source.id}`}
                      className="text-sm font-medium leading-none cursor-pointer flex-1"
                    >
                      {source.name}
                      <span className="block text-xs text-muted-foreground">
                        {source.type}
                      </span>
                    </label>
                  </div>
                ))}
                {(!sources || sources.length === 0) && (
                  <p className="text-sm text-muted-foreground col-span-full text-center py-4">
                    No sources available
                  </p>
                )}
              </div>
              {selectedSources.length > 0 && (
                <p className="text-sm text-muted-foreground">
                  {selectedSources.length} source(s) selected
                </p>
              )}
            </div>

            {/* Rate Limit & Expiration */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rate-limit">Rate Limit (requests/min)</Label>
                <Input
                  id="rate-limit"
                  type="number"
                  min="1"
                  max="10000"
                  value={rateLimit}
                  onChange={(e) => setRateLimit(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expires">Expires In (days)</Label>
                <Input
                  id="expires"
                  type="number"
                  min="1"
                  max="365"
                  placeholder="Never"
                  value={expiresInDays}
                  onChange={(e) => setExpiresInDays(e.target.value)}
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-4 pt-4">
              <Button
                onClick={handleCreate}
                disabled={!newTokenName || createMutation.isPending}
              >
                {createMutation.isPending ? "Creating..." : "Create Token"}
              </Button>
              <Button variant="outline" onClick={() => {
                setShowCreate(false);
                setNewTokenName("");
                setSelectedSources([]);
                setExpiresInDays("");
                setRateLimit("100");
              }}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Created Token Display */}
      {createdToken && (
        <Card className="mb-6 border-green-200 bg-green-50">
          <CardHeader>
            <CardTitle className="text-green-800">Token Created</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 text-sm text-green-700">
              Copy this token now - it won't be shown again!
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded bg-white p-2 font-mono text-sm">
                {createdToken}
              </code>
              <Button size="sm" onClick={copyToken}>
                {copied ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <Button
              className="mt-4"
              variant="outline"
              onClick={() => setCreatedToken(null)}
            >
              Done
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Tokens List */}
      <Card>
        <CardHeader>
          <CardTitle>Active Tokens</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Rate Limit</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tokens?.map((token: any) => (
                <TableRow key={token.id}>
                  <TableCell className="font-medium">{token.name}</TableCell>
                  <TableCell>
                    <code className="text-sm">{token.token_preview}...</code>
                  </TableCell>
                  <TableCell>
                    {token.source_ids?.length > 0 ? (
                      <Badge variant="outline" className="font-normal">
                        {token.source_ids.length} source(s)
                      </Badge>
                    ) : (
                      <Badge variant="secondary">All sources</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={token.is_active ? "success" : "destructive"}
                    >
                      {token.is_active ? "Active" : "Revoked"}
                    </Badge>
                  </TableCell>
                  <TableCell>{token.rate_limit}/min</TableCell>
                  <TableCell>
                    {token.expires_at ? formatDate(token.expires_at) : "Never"}
                  </TableCell>
                  <TableCell>
                    {token.last_used_at
                      ? formatDate(token.last_used_at)
                      : "Never"}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => revokeMutation.mutate(token.id)}
                      disabled={revokeMutation.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {(!tokens || tokens.length === 0) && (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="text-center text-muted-foreground"
                  >
                    No tokens created
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
