import { useState } from 'react';
import { PackageOpen, AlertCircle } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { StatusBadge } from './StatusBadge';
import type { Resource } from '../lib/api';

interface DeploymentsTableProps {
  resources: Resource[];
  isLoading: boolean;
  isError: boolean;
}

export function DeploymentsTable({ resources, isLoading, isError }: DeploymentsTableProps) {
  const [envFilter, setEnvFilter] = useState<string>('All');

  const filtered = envFilter === 'All'
    ? resources
    : resources.filter((r) => r.env === envFilter);

  return (
    <div className="space-y-4">
      {/* Environment filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">Environment</span>
        <Select value={envFilter} onValueChange={(v) => { if (v !== null) setEnvFilter(v); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All</SelectItem>
            <SelectItem value="dev">dev</SelectItem>
            <SelectItem value="staging">staging</SelectItem>
            <SelectItem value="prod">prod</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Name</TableHead>
            <TableHead className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Kind</TableHead>
            <TableHead className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Status</TableHead>
            <TableHead className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Environment</TableHead>
            <TableHead className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Project</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <>
              {[1, 2, 3].map((i) => (
                <TableRow key={i} className="min-h-[44px]">
                  <TableCell><Skeleton className="h-4 w-full" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-full" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-full" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-full" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-full" /></TableCell>
                </TableRow>
              ))}
            </>
          ) : isError ? null : (
            filtered.map((r) => (
              <TableRow key={r.id} className="hover:bg-muted/50 min-h-[44px]">
                <TableCell>{r.name}</TableCell>
                <TableCell>{r.kind}</TableCell>
                <TableCell><StatusBadge status={r.status} /></TableCell>
                <TableCell>{r.env ?? '—'}</TableCell>
                <TableCell>{r.project ?? '—'}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Empty state */}
      {!isLoading && !isError && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <PackageOpen className="h-12 w-12 text-muted-foreground" />
          <div className="text-center">
            <p className="text-base font-semibold text-foreground">No resources found</p>
            <p className="text-sm text-muted-foreground mt-1">
              Select a different team or run the seed script to populate data.
            </p>
          </div>
        </div>
      )}

      {/* Error state */}
      {!isLoading && isError && (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div className="text-center">
            <p className="text-base font-semibold text-foreground">Failed to load resources</p>
            <p className="text-sm text-muted-foreground mt-1">
              Check that the PECP API is running on port 8000, then click Refresh.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
