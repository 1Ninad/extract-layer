import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export function UploadIcon(props: IconProps) { return <svg {...base} {...props}><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5"/><path d="M5 15v4h14v-4"/></svg>; }
export function FileIcon(props: IconProps) { return <svg {...base} {...props}><path d="M6 2.8h8l4 4V21H6z"/><path d="M14 2.8v4h4M9 12h6M9 16h5"/></svg>; }
export function DownloadIcon(props: IconProps) { return <svg {...base} {...props}><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 20h14"/></svg>; }
export function TrashIcon(props: IconProps) { return <svg {...base} {...props}><path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7m4 4v6m4-6v6"/></svg>; }
export function PlusIcon(props: IconProps) { return <svg {...base} {...props}><path d="M12 5v14M5 12h14"/></svg>; }
export function CheckIcon(props: IconProps) { return <svg {...base} {...props}><path d="m5 12 4 4L19 6"/></svg>; }
