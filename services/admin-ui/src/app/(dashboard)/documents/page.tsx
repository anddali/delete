"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { documentsApi, sourcesApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
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
import {
  FileText,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  Search,
  Layers,
} from "lucide-react";

interface Document {
  id: string;
  source_id: string;
  source_name: string | null;
  external_id: string;
  title: string;
  content_preview: string;
  content_length: number;
  url: string | null;
  chunk_count: number;
  indexed_at: string;
  created_at: string;
  updated_at: string;
}

interface Chunk {
  id: string;
  document_id: string;
  position: number;
  content: string;
  char_start: number;
  char_end: number;
  char_count: number;
  has_embedding: boolean;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");

  // Document detail dialog
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(
    null
  );
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Chunks dialog
  const [chunksDocId, setChunksDocId] = useState<string | null>(null);
  const [chunksPage, setChunksPage] = useState(1);
  const [isChunksOpen, setIsChunksOpen] = useState(false);

  // Fetch sources for filter dropdown
  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: sourcesApi.list,
  });

  // Fetch documents
  const { data: documentsData, isLoading } = useQuery({
    queryKey: ["documents", sourceFilter, searchQuery, page, pageSize],
    queryFn: () =>
      documentsApi.list({
        source_id: sourceFilter !== "all" ? sourceFilter : undefined,
        search: searchQuery || undefined,
        page,
        page_size: pageSize,
      }),
  });

  // Fetch document detail
  const { data: documentDetail } = useQuery({
    queryKey: ["document", selectedDocument?.id],
    queryFn: () =>
      selectedDocument ? documentsApi.get(selectedDocument.id) : null,
    enabled: !!selectedDocument && isDetailOpen,
  });

  // Fetch chunks
  const { data: chunksData, isLoading: chunksLoading } = useQuery({
    queryKey: ["chunks", chunksDocId, chunksPage],
    queryFn: () =>
      chunksDocId
        ? documentsApi.getChunks(chunksDocId, {
            page: chunksPage,
            page_size: 10,
          })
        : null,
    enabled: !!chunksDocId && isChunksOpen,
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: documentsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(searchInput);
    setPage(1);
  };

  const openChunksDialog = (doc: Document) => {
    setChunksDocId(doc.id);
    setChunksPage(1);
    setIsChunksOpen(true);
  };

  const openDetailDialog = (doc: Document) => {
    setSelectedDocument(doc);
    setIsDetailOpen(true);
  };

  if (isLoading) {
    return <div className="p-8">Loading...</div>;
  }

  const documents: Document[] = documentsData?.items || [];
  const totalPages = documentsData?.pages || 1;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Documents</h1>
        <p className="text-gray-500 mt-1">
          View and manage uploaded documents and their chunks
        </p>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <form onSubmit={handleSearch} className="flex gap-2">
                <Input
                  placeholder="Search by title..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="flex-1"
                />
                <Button type="submit" variant="outline">
                  <Search className="h-4 w-4" />
                </Button>
              </form>
            </div>
            <div className="w-[200px]">
              <Select
                value={sourceFilter}
                onValueChange={(value) => {
                  setSourceFilter(value);
                  setPage(1);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Filter by source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sources</SelectItem>
                  {sources?.map((source: { id: string; name: string }) => (
                    <SelectItem key={source.id} value={source.id}>
                      {source.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Documents Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Documents ({documentsData?.total || 0})</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead>Indexed</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-gray-400" />
                      <div>
                        <div className="font-medium truncate max-w-[300px]">
                          {doc.title}
                        </div>
                        <div className="text-xs text-gray-400 truncate max-w-[300px]">
                          {doc.content_preview}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{doc.source_name || "N/A"}</Badge>
                  </TableCell>
                  <TableCell>
                    {(doc.content_length / 1024).toFixed(1)} KB
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={doc.chunk_count > 0 ? "default" : "secondary"}
                    >
                      {doc.chunk_count} chunks
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {formatDate(doc.indexed_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        title="View Details"
                        onClick={() => openDetailDialog(doc)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        title="View Chunks"
                        onClick={() => openChunksDialog(doc)}
                        disabled={doc.chunk_count === 0}
                      >
                        <Layers className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        title="Delete"
                        onClick={() => {
                          if (
                            confirm(
                              `Delete "${doc.title}"? This will also delete all its chunks.`
                            )
                          ) {
                            deleteMutation.mutate(doc.id);
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
              {documents.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center text-gray-400 py-8"
                  >
                    No documents found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <div className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Document Detail Dialog */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Document Details</DialogTitle>
            <DialogDescription>
              {selectedDocument?.title}
            </DialogDescription>
          </DialogHeader>
          {documentDetail && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Source:</span>{" "}
                  {documentDetail.source_name || "N/A"}
                </div>
                <div>
                  <span className="text-gray-500">Chunks:</span>{" "}
                  {documentDetail.chunk_count}
                </div>
                <div>
                  <span className="text-gray-500">Indexed:</span>{" "}
                  {formatDate(documentDetail.indexed_at)}
                </div>
                <div>
                  <span className="text-gray-500">Size:</span>{" "}
                  {(documentDetail.content.length / 1024).toFixed(1)} KB
                </div>
                {documentDetail.url && (
                  <div className="col-span-2">
                    <span className="text-gray-500">URL:</span>{" "}
                    <span className="break-all">{documentDetail.url}</span>
                  </div>
                )}
              </div>

              {documentDetail.metadata && (
                <div>
                  <span className="text-gray-500 text-sm">Metadata:</span>
                  <pre className="mt-1 p-3 bg-gray-50 rounded-md text-xs overflow-x-auto">
                    {JSON.stringify(documentDetail.metadata, null, 2)}
                  </pre>
                </div>
              )}

              <div>
                <span className="text-gray-500 text-sm">Content:</span>
                <pre className="mt-1 p-3 bg-gray-50 rounded-md text-sm whitespace-pre-wrap max-h-[400px] overflow-y-auto">
                  {documentDetail.content}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Chunks Dialog */}
      <Dialog open={isChunksOpen} onOpenChange={setIsChunksOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Document Chunks</DialogTitle>
            <DialogDescription>
              {chunksData?.total || 0} chunks total
            </DialogDescription>
          </DialogHeader>

          {chunksLoading ? (
            <div className="py-8 text-center text-gray-400">
              Loading chunks...
            </div>
          ) : (
            <div className="space-y-4">
              {chunksData?.items?.map((chunk: Chunk) => (
                <div
                  key={chunk.id}
                  className="border rounded-lg p-4 bg-gray-50"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">
                        Position {chunk.position}
                      </Badge>
                      <span className="text-xs text-gray-400">
                        chars {chunk.char_start}-{chunk.char_end} (
                        {chunk.char_count} chars)
                      </span>
                    </div>
                    <Badge
                      variant={chunk.has_embedding ? "default" : "secondary"}
                    >
                      {chunk.has_embedding ? "Embedded" : "No embedding"}
                    </Badge>
                  </div>
                  <pre className="text-sm whitespace-pre-wrap bg-white p-3 rounded border">
                    {chunk.content}
                  </pre>
                </div>
              ))}

              {chunksData?.items?.length === 0 && (
                <div className="py-8 text-center text-gray-400">
                  No chunks found.
                </div>
              )}

              {/* Chunks Pagination */}
              {chunksData && chunksData.pages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t">
                  <div className="text-sm text-gray-500">
                    Page {chunksPage} of {chunksData.pages}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={chunksPage <= 1}
                      onClick={() => setChunksPage((p) => p - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={chunksPage >= chunksData.pages}
                      onClick={() => setChunksPage((p) => p + 1)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
