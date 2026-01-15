"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { sourcesApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Plus, Play, Trash2, RefreshCw, Upload } from "lucide-react";

export default function SourcesPage() {
  const queryClient = useQueryClient();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);
  const [uploadSourceId, setUploadSourceId] = useState<string | null>(null);
  const [uploadSourceName, setUploadSourceName] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadError, setUploadError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [newSource, setNewSource] = useState({
    name: "",
    type: "confluence",
    description: "",
    // Confluence settings
    confluence_base_url: "",
    confluence_space_keys: "",
    confluence_username: "",
    confluence_api_token: "",
    // Slack settings
    slack_bot_token: "",
    slack_channel_ids: "",
    // Chunking settings
    chunk_size: 1000,
    respect_boundaries: true,
  });
  const [error, setError] = useState("");

  const { data: sources, isLoading } = useQuery({
    queryKey: ["sources"],
    queryFn: sourcesApi.list,
  });

  const createMutation = useMutation({
    mutationFn: sourcesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setIsAddDialogOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to create source");
    },
  });

  const syncMutation = useMutation({
    mutationFn: ({ id, fullSync }: { id: string; fullSync: boolean }) =>
      sourcesApi.sync(id, fullSync),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: sourcesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ sourceId, files }: { sourceId: string; files: File[] }) =>
      sourcesApi.uploadFiles(sourceId, files),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setIsUploadDialogOpen(false);
      setSelectedFiles([]);
      setUploadSourceId(null);
      alert(
        `Uploaded ${data.total_uploaded} file(s) successfully!${
          data.total_errors > 0 ? ` (${data.total_errors} errors)` : ""
        }`
      );
    },
    onError: (err: any) => {
      setUploadError(err.response?.data?.detail || "Failed to upload files");
    },
  });

  const processMutation = useMutation({
    mutationFn: sourcesApi.processUploads,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const openUploadDialog = (sourceId: string, sourceName: string) => {
    setUploadSourceId(sourceId);
    setUploadSourceName(sourceName);
    setSelectedFiles([]);
    setUploadError("");
    setIsUploadDialogOpen(true);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadSourceId || selectedFiles.length === 0) return;
    setUploadError("");
    uploadMutation.mutate({ sourceId: uploadSourceId, files: selectedFiles });
  };

  const resetForm = () => {
    setNewSource({
      name: "",
      type: "confluence",
      description: "",
      confluence_base_url: "",
      confluence_space_keys: "",
      confluence_username: "",
      confluence_api_token: "",
      slack_bot_token: "",
      slack_channel_ids: "",
      chunk_size: 1000,
      respect_boundaries: true,
    });
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Build the request based on source type
    const payload: any = {
      name: newSource.name,
      type: newSource.type,
      description: newSource.description || undefined,
      chunking_config: {
        chunk_size_chars: newSource.chunk_size,
        respect_boundaries: newSource.respect_boundaries,
      },
    };

    if (newSource.type === "confluence") {
      payload.config = {
        base_url: newSource.confluence_base_url,
        space_keys: newSource.confluence_space_keys
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      payload.credentials = {
        username: newSource.confluence_username,
        api_token: newSource.confluence_api_token,
      };
    } else if (newSource.type === "slack") {
      payload.config = {
        channel_ids: newSource.slack_channel_ids
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      payload.credentials = {
        bot_token: newSource.slack_bot_token,
      };
    } else if (newSource.type === "file_upload") {
      payload.config = {};
      payload.credentials = {};
    }

    createMutation.mutate(payload);
  };

  const sourceTypeColors: Record<string, string> = {
    confluence: "bg-blue-100 text-blue-800",
    slack: "bg-purple-100 text-purple-800",
    file_upload: "bg-green-100 text-green-800",
  };

  if (isLoading) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Sources</h1>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Source
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Knowledge Source</DialogTitle>
              <DialogDescription>
                Configure a new knowledge source to ingest documents from.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit}>
              {error && (
                <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800">
                  {error}
                </div>
              )}

              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Source Name</Label>
                  <Input
                    id="name"
                    value={newSource.name}
                    onChange={(e) =>
                      setNewSource({ ...newSource, name: e.target.value })
                    }
                    placeholder="e.g., Engineering Docs"
                    required
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="type">Source Type</Label>
                  <Select
                    value={newSource.type}
                    onValueChange={(value) =>
                      setNewSource({ ...newSource, type: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="confluence">Confluence</SelectItem>
                      <SelectItem value="slack">Slack</SelectItem>
                      <SelectItem value="file_upload">File Upload</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="description">Description (optional)</Label>
                  <Input
                    id="description"
                    value={newSource.description}
                    onChange={(e) =>
                      setNewSource({
                        ...newSource,
                        description: e.target.value,
                      })
                    }
                    placeholder="Brief description of this source"
                  />
                </div>

                {/* Confluence Settings */}
                {newSource.type === "confluence" && (
                  <>
                    <div className="border-t pt-4">
                      <h4 className="font-medium mb-3">Confluence Settings</h4>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="confluence_base_url">Base URL</Label>
                      <Input
                        id="confluence_base_url"
                        value={newSource.confluence_base_url}
                        onChange={(e) =>
                          setNewSource({
                            ...newSource,
                            confluence_base_url: e.target.value,
                          })
                        }
                        placeholder="https://your-domain.atlassian.net/wiki"
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="confluence_space_keys">
                        Space Keys (comma-separated)
                      </Label>
                      <Input
                        id="confluence_space_keys"
                        value={newSource.confluence_space_keys}
                        onChange={(e) =>
                          setNewSource({
                            ...newSource,
                            confluence_space_keys: e.target.value,
                          })
                        }
                        placeholder="ENG, DOCS, WIKI"
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="confluence_username">
                        Username/Email
                      </Label>
                      <Input
                        id="confluence_username"
                        value={newSource.confluence_username}
                        onChange={(e) =>
                          setNewSource({
                            ...newSource,
                            confluence_username: e.target.value,
                          })
                        }
                        placeholder="your-email@company.com"
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="confluence_api_token">API Token</Label>
                      <Input
                        id="confluence_api_token"
                        type="password"
                        value={newSource.confluence_api_token}
                        onChange={(e) =>
                          setNewSource({
                            ...newSource,
                            confluence_api_token: e.target.value,
                          })
                        }
                        placeholder="Your Atlassian API token"
                        required
                      />
                    </div>
                  </>
                )}

                {/* Slack Settings */}
                {newSource.type === "slack" && (
                  <>
                    <div className="border-t pt-4">
                      <h4 className="font-medium mb-3">Slack Settings</h4>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="slack_bot_token">Bot Token</Label>
                      <Input
                        id="slack_bot_token"
                        type="password"
                        value={newSource.slack_bot_token}
                        onChange={(e) =>
                          setNewSource({
                            ...newSource,
                            slack_bot_token: e.target.value,
                          })
                        }
                        placeholder="xoxb-..."
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="slack_channel_ids">
                        Channel IDs (comma-separated)
                      </Label>
                      <Input
                        id="slack_channel_ids"
                        value={newSource.slack_channel_ids}
                        onChange={(e) =>
                          setNewSource({
                            ...newSource,
                            slack_channel_ids: e.target.value,
                          })
                        }
                        placeholder="C01234567, C09876543"
                        required
                      />
                    </div>
                  </>
                )}

                {/* File Upload Info */}
                {newSource.type === "file_upload" && (
                  <div className="border-t pt-4">
                    <p className="text-sm text-gray-500">
                      After creating this source, you can upload files directly
                      through the API or use the upload feature.
                    </p>
                  </div>
                )}

                {/* Chunking Settings */}
                <div className="border-t pt-4">
                  <h4 className="font-medium mb-3">Chunking Settings</h4>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="chunk_size">Chunk Size (characters)</Label>
                  <Input
                    id="chunk_size"
                    type="number"
                    value={newSource.chunk_size}
                    onChange={(e) =>
                      setNewSource({
                        ...newSource,
                        chunk_size: parseInt(e.target.value) || 1000,
                      })
                    }
                    min={200}
                    max={4000}
                  />
                  <p className="text-xs text-gray-500">
                    Recommended: 800-1200 characters. No overlap is applied
                    during indexing.
                  </p>
                </div>
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setIsAddDialogOpen(false);
                    resetForm();
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Creating..." : "Create Source"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Knowledge Sources</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Documents</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead>Last Sync</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sources?.map((source: any) => (
                <TableRow key={source.id}>
                  <TableCell className="font-medium">{source.name}</TableCell>
                  <TableCell>
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        sourceTypeColors[source.type] ||
                        "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {source.type}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={source.is_active ? "default" : "secondary"}>
                      {source.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {source.document_count?.toLocaleString() || 0}
                  </TableCell>
                  <TableCell>
                    {source.chunk_count?.toLocaleString() || 0}
                  </TableCell>
                  <TableCell>
                    {source.last_sync_at ? (
                      <div>
                        <div className="text-sm">
                          {formatDate(source.last_sync_at)}
                        </div>
                        <Badge
                          variant={
                            source.last_sync_status === "success"
                              ? "default"
                              : source.last_sync_status === "failed"
                              ? "destructive"
                              : "secondary"
                          }
                          className="mt-1"
                        >
                          {source.last_sync_status || "pending"}
                        </Badge>
                      </div>
                    ) : (
                      <span className="text-gray-400">Never</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      {source.type === "file_upload" && (
                        <Button
                          size="sm"
                          variant="outline"
                          title="Upload Files"
                          onClick={() =>
                            openUploadDialog(source.id, source.name)
                          }
                        >
                          <Upload className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        title="Incremental Sync"
                        onClick={() =>
                          syncMutation.mutate({
                            id: source.id,
                            fullSync: false,
                          })
                        }
                        disabled={syncMutation.isPending}
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        title="Full Sync"
                        onClick={() =>
                          syncMutation.mutate({ id: source.id, fullSync: true })
                        }
                        disabled={syncMutation.isPending}
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        title="Delete"
                        onClick={() => {
                          if (
                            confirm(
                              `Delete source "${source.name}"? This will also delete all its documents and chunks.`
                            )
                          ) {
                            deleteMutation.mutate(source.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {(!sources || sources.length === 0) && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center text-gray-400 py-8"
                  >
                    No sources configured. Click &quot;Add Source&quot; to get
                    started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Upload Files Dialog */}
      <Dialog open={isUploadDialogOpen} onOpenChange={setIsUploadDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Upload Files</DialogTitle>
            <DialogDescription>
              Upload documents to &quot;{uploadSourceName}&quot;
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleUploadSubmit}>
            {uploadError && (
              <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-800">
                {uploadError}
              </div>
            )}

            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="files">Select Files</Label>
                <Input
                  id="files"
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".txt,.md,.pdf,.docx,.doc,.html,.json,.csv,.xml"
                  onChange={handleFileSelect}
                  required
                />
                <p className="text-xs text-gray-500">
                  Supported: .txt, .md, .pdf, .docx, .doc, .html, .json, .csv,
                  .xml
                </p>
              </div>

              {selectedFiles.length > 0 && (
                <div className="border rounded-md p-3 bg-gray-50">
                  <p className="text-sm font-medium mb-2">
                    Selected files ({selectedFiles.length}):
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 max-h-40 overflow-y-auto">
                    {selectedFiles.map((file, idx) => (
                      <li key={idx} className="flex justify-between">
                        <span className="truncate">{file.name}</span>
                        <span className="text-gray-400 ml-2">
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setIsUploadDialogOpen(false);
                  setSelectedFiles([]);
                }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  uploadMutation.isPending || selectedFiles.length === 0
                }
              >
                {uploadMutation.isPending
                  ? "Uploading..."
                  : `Upload ${selectedFiles.length} File${
                      selectedFiles.length !== 1 ? "s" : ""
                    }`}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
