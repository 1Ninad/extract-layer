import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const baseProps = { viewBox: "0 0 15 15", fill: "none", stroke: "currentColor", strokeWidth: 1.35, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function FileTextIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M3.5 1.5h5l3 3v9h-8z" /><path d="M8.5 1.5v3h3M5.5 7.5h4M5.5 10h4" /></svg>;
}

export function UploadIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M7.5 10.5v-7M4.5 6.5l3-3 3 3M3 11.5v2h9v-2" /></svg>;
}

export function Pencil1Icon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="m9.7 2.1 3.2 3.2-6.7 6.8-3.6.5.5-3.6zM8.4 3.4l3.2 3.2" /></svg>;
}

export function ReloadIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M12 5.5V2.5M12 2.5H9M12 2.5 10 4.5A5 5 0 1 0 12.3 9" /></svg>;
}

export function ArrowRightIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M2.5 7.5h10M8.5 3.5l4 4-4 4" /></svg>;
}

export function ArrowLeftIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M12.5 7.5h-10M6.5 3.5l-4 4 4 4" /></svg>;
}

export function LightningBoltIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M8.5 1.5 3.5 8h3l-1 5 5-6.5h-3z" /></svg>;
}

export function CheckCircledIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><circle cx="7.5" cy="7.5" r="5.5" /><path d="m5 7.5 1.7 1.7L10.5 5.5" /></svg>;
}

export function DownloadIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M7.5 2.5v7M4.5 7.5l3 3 3-3M3 12.5h9" /></svg>;
}

export function ChevronDownIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="m3.5 5.5 4 4 4-4" /></svg>;
}

export function InfoCircledIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><circle cx="7.5" cy="7.5" r="5.5" /><path d="M7.5 6.7v3.5M7.5 4.7v.3" /></svg>;
}

export function Cross2Icon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="m4 4 7 7M11 4l-7 7" /></svg>;
}

export function PlusIcon(props: IconProps) {
  return <svg {...baseProps} {...props} aria-hidden={props["aria-hidden"] ?? true}><path d="M7.5 3v9M3 7.5h9" /></svg>;
}
