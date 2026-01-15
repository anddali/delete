"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.list,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      settingsApi.update(key, value),
    onSuccess: () => {
      setEditingKey(null);
      setEditValue("");
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const startEdit = (key: string, currentValue: string) => {
    setEditingKey(key);
    setEditValue(currentValue);
  };

  const saveEdit = () => {
    if (editingKey) {
      updateMutation.mutate({ key: editingKey, value: editValue });
    }
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1 className="mb-6 text-3xl font-bold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>System Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {settings?.map((setting: any) => (
              <div
                key={setting.key}
                className="flex items-center justify-between border-b pb-4"
              >
                <div className="flex-1">
                  <p className="font-medium">{setting.key}</p>
                  {setting.description && (
                    <p className="text-sm text-muted-foreground">
                      {setting.description}
                    </p>
                  )}
                </div>

                {editingKey === setting.key ? (
                  <div className="flex gap-2">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="w-64"
                      type={setting.is_secret ? "password" : "text"}
                    />
                    <Button size="sm" onClick={saveEdit}>
                      Save
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEditingKey(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-4">
                    <code className="rounded bg-gray-100 px-2 py-1 text-sm">
                      {setting.value}
                    </code>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => startEdit(setting.key, setting.value)}
                    >
                      Edit
                    </Button>
                  </div>
                )}
              </div>
            ))}

            {(!settings || settings.length === 0) && (
              <p className="text-center text-muted-foreground">
                No settings configured
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
