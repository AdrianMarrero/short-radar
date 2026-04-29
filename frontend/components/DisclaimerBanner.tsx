export function DisclaimerBanner() {
  return (
    <div className="bg-ink text-paper text-xs py-2 px-6">
      <div className="max-w-[1400px] mx-auto flex items-center gap-3">
        <span className="font-mono uppercase tracking-widest">⚠ Disclaimer</span>
        <span className="text-paper/80">
          Esta herramienta es de análisis. <strong>NO es asesoramiento financiero.</strong>{" "}
          Operar en corto tiene riesgo elevado y las pérdidas pueden superar el capital invertido. Decide y opera bajo tu propia responsabilidad.
        </span>
      </div>
    </div>
  );
}
