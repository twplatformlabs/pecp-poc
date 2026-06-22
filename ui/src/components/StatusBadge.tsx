// Colors match CLI STATUS_COLORS exactly (src/pecp/cli/main.py:40-45)
// pending=yellow/amber, provisioning=blue, ready=green, failed=red
// Do NOT use shadcn Badge with variant prop — defaults do not match CLI palette (UI-SPEC prohibition)

export const STATUS_CLASSES: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700',
  provisioning: 'bg-blue-100 text-blue-700',
  ready: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_CLASSES[status] ?? 'bg-slate-100 text-slate-600';
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
