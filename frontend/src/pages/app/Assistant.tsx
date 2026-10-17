import { Sparkles } from "lucide-react";
import { SpiChat } from "../../components/SpiChat";
import { Card } from "../../components/ui";
import { useWorkgroups } from "../../context/workgroup";

export default function Assistant() {
  const { workgroup } = useWorkgroups();
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center gap-4">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-ink text-brand dark:bg-raised">
          <Sparkles size={22} />
        </span>
        <div>
          <h1 className="text-[28px] font-semibold leading-tight">SPI</h1>
          <p className="text-[13.5px] text-ink-2">{workgroup ? `Your payroll assistant, working in ${workgroup.name}.` : "Your payroll assistant."}</p>
        </div>
      </div>
      <Card className="flex h-[calc(100vh-240px)] min-h-[520px] flex-col overflow-hidden">
        <SpiChat workgroupId={workgroup?.id ?? null} />
      </Card>
    </div>
  );
}
