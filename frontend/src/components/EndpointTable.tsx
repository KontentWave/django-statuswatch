import { useEffect, useMemo } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import type { EndpointDto } from "@/lib/endpoint-client";
import { logDashboardEvent } from "@/lib/dashboard-logger";

interface EndpointTableProps {
  rows: EndpointDto[];
  page: number;
  totalPages: number;
  totalCount: number;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  isSuccess: boolean;
  errorMessage?: string | null;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  onPageChange: (nextPage: number) => void;
  onDelete: (endpointId: string) => void;
  pendingDeleteId?: string;
  isDeletePending?: boolean;
  emptyMessage?: string;
}

const columnHelper = createColumnHelper<EndpointDto>();
type ColumnMetaProps = {
  headerClassName?: string;
  cellClassName?: string;
};

export default function EndpointTable({
  rows,
  page,
  totalPages,
  totalCount,
  isLoading,
  isFetching,
  isError,
  isSuccess,
  errorMessage,
  hasNextPage,
  hasPreviousPage,
  onPageChange,
  onDelete,
  pendingDeleteId,
  isDeletePending,
  emptyMessage = "No endpoints yet. Add your first one below.",
}: EndpointTableProps) {
  const rowCount = rows.length;

  useEffect(() => {
    if (!isSuccess || isFetching) {
      return;
    }

    void logDashboardEvent({
      event: "pagination",
      phase: "success",
      page,
      pageSize: rowCount,
      totalCount,
      hasNextPage,
      hasPreviousPage,
    });
  }, [
    hasNextPage,
    hasPreviousPage,
    isFetching,
    isSuccess,
    page,
    rowCount,
    totalCount,
  ]);

  useEffect(() => {
    if (!isError || !errorMessage) {
      return;
    }

    void logDashboardEvent({
      event: "pagination",
      phase: "error",
      page,
      message: errorMessage,
    });
  }, [errorMessage, isError, page]);

  const columns = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Name",
        cell: ({ getValue }) => getValue() || "—",
        meta: {
          headerClassName: "px-4 py-3",
          cellClassName: "px-4 py-3 font-medium text-foreground",
        } satisfies ColumnMetaProps,
      }),
      columnHelper.accessor("url", {
        header: "URL",
        cell: ({ getValue }) => (
          <span className="break-all text-sm text-foreground">
            {getValue()}
          </span>
        ),
        meta: {
          headerClassName: "px-4 py-3",
          cellClassName: "px-4 py-3",
        } satisfies ColumnMetaProps,
      }),
      columnHelper.accessor("last_status", {
        header: "Status",
        cell: ({ getValue }) => (
          <span className="text-sm text-muted-foreground">
            {getValue() || "pending"}
          </span>
        ),
        meta: {
          headerClassName: "px-4 py-3",
          cellClassName: "px-4 py-3",
        } satisfies ColumnMetaProps,
      }),
      columnHelper.accessor("interval_minutes", {
        header: "Interval (min)",
        cell: ({ getValue }) => (
          <span className="text-sm text-muted-foreground">{getValue()}</span>
        ),
        meta: {
          headerClassName: "px-4 py-3",
          cellClassName: "px-4 py-3",
        } satisfies ColumnMetaProps,
      }),
      columnHelper.accessor("last_checked_at", {
        header: "Last Checked",
        cell: ({ row, getValue }) => {
          const lastCheckedAt = getValue();
          const lastEnqueuedAt = row.original.last_enqueued_at;
          const enqueuedDate = lastEnqueuedAt ? new Date(lastEnqueuedAt) : null;
          const checkedDate = lastCheckedAt ? new Date(lastCheckedAt) : null;

          if (
            enqueuedDate &&
            (!checkedDate || enqueuedDate.getTime() > checkedDate.getTime())
          ) {
            return (
              <span className="flex flex-col text-sm text-muted-foreground">
                <span>Queued {enqueuedDate.toLocaleTimeString()}</span>
                {checkedDate ? (
                  <span className="text-xs">
                    Last {checkedDate.toLocaleString()}
                  </span>
                ) : null}
              </span>
            );
          }

          if (checkedDate) {
            return (
              <span className="text-sm text-muted-foreground">
                {checkedDate.toLocaleString()}
              </span>
            );
          }

          return <span className="text-sm text-muted-foreground">Never</span>;
        },
        meta: {
          headerClassName: "px-4 py-3",
          cellClassName: "px-4 py-3",
        } satisfies ColumnMetaProps,
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          const endpoint = row.original;
          const disabled = Boolean(
            isDeletePending && pendingDeleteId === endpoint.id
          );
          return (
            <button
              type="button"
              onClick={() => onDelete(endpoint.id)}
              disabled={disabled}
              className="inline-flex items-center rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive transition hover:bg-destructive/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-destructive focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {disabled ? "Removing…" : "Delete"}
            </button>
          );
        },
        meta: {
          headerClassName: "px-4 py-3 text-right",
          cellClassName: "px-4 py-3 text-right",
        } satisfies ColumnMetaProps,
      }),
    ],
    [isDeletePending, onDelete, pendingDeleteId]
  );

  const tableData = useMemo(() => rows, [rows]);

  const table = useReactTable({
    data: tableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading endpoints…</p>;
  }

  if (isError) {
    return (
      <p className="text-sm text-red-600">
        {errorMessage ?? "Unable to load endpoints."}
      </p>
    );
  }

  if (!rowCount) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  const canGoPrev = page > 1 && !isFetching && hasPreviousPage;
  const canGoNext =
    page < totalPages && !isFetching && hasNextPage && totalPages > 1;

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-md border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={
                      (
                        header.column.columnDef.meta as
                          | ColumnMetaProps
                          | undefined
                      )?.headerClassName ?? "px-4 py-3"
                    }
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="bg-background">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={
                      (
                        cell.column.columnDef.meta as
                          | ColumnMetaProps
                          | undefined
                      )?.cellClassName ?? "px-4 py-3"
                    }
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!canGoPrev}
          className="inline-flex items-center rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!canGoNext}
          className="inline-flex items-center rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
