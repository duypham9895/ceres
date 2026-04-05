import * as Popover from '@radix-ui/react-popover';
import type { ReactNode } from 'react';

interface FilterPopoverProps {
  readonly trigger: ReactNode;
  readonly children: ReactNode;
  readonly open?: boolean;
  readonly onOpenChange?: (open: boolean) => void;
  readonly align?: 'start' | 'center' | 'end';
  readonly minWidth?: number;
}

export default function FilterPopover({
  trigger,
  children,
  open,
  onOpenChange,
  align = 'start',
  minWidth = 220,
}: FilterPopoverProps) {
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align={align}
          sideOffset={6}
          className="z-50 bg-bg-card border border-border rounded-lg p-2 shadow-xl shadow-black/30 animate-in fade-in-0 zoom-in-95"
          style={{ minWidth }}
        >
          {children}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
