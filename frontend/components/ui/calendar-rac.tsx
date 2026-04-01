"use client";

import { cn } from "../../lib/utils";
import { getLocalTimeZone, today } from "@internationalized/date";
import { ComponentProps, useMemo } from "react";
import {
  Button,
  CalendarCell as CalendarCellRac,
  CalendarGridBody as CalendarGridBodyRac,
  CalendarGridHeader as CalendarGridHeaderRac,
  CalendarGrid as CalendarGridRac,
  CalendarHeaderCell as CalendarHeaderCellRac,
  Calendar as CalendarRac,
  Heading as HeadingRac,
  RangeCalendar as RangeCalendarRac,
  composeRenderProps,
} from "react-aria-components";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Event } from "../../types";

interface BaseCalendarProps {
  className?: string;
  events?: Event[];
}

type CalendarProps = ComponentProps<typeof CalendarRac> & BaseCalendarProps;
type RangeCalendarProps = ComponentProps<typeof RangeCalendarRac> & BaseCalendarProps;

/* ── Category dot colors (matches app structure) ── */
const CATEGORY_DOT_COLORS: Record<string, string> = {
  kultura: "bg-violet-400",
  sport: "bg-orange-400",
  rozrywka: "bg-pink-400",
  społeczne: "bg-emerald-400",
  edukacja: "bg-cyan-400",
  koncert: "bg-rose-400",
  festiwal: "bg-fuchsia-400",
  targi: "bg-amber-400",
  urząd: "bg-blue-400",
};

const getCategoryDotColor = (category?: string): string => {
  if (!category) return "bg-blue-400";
  const key = category.toLowerCase();
  for (const [k, v] of Object.entries(CATEGORY_DOT_COLORS)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return "bg-blue-400";
};

/* ── Header ── */
const CalendarHeader = () => (
  <header className="flex w-full items-center gap-1 pb-2">
    <Button
      slot="previous"
      className="flex size-8 items-center justify-center rounded-lg text-neutral-400 outline-none transition-colors hover:bg-white/10 hover:text-neutral-200 focus-visible:ring-1 focus-visible:ring-blue-500"
    >
      <ChevronLeft size={16} />
    </Button>
    <HeadingRac className="grow text-center text-sm font-bold text-neutral-200" />
    <Button
      slot="next"
      className="flex size-8 items-center justify-center rounded-lg text-neutral-400 outline-none transition-colors hover:bg-white/10 hover:text-neutral-200 focus-visible:ring-1 focus-visible:ring-blue-500"
    >
      <ChevronRight size={16} />
    </Button>
  </header>
);

/* ── Calendar grid with event dots ── */
interface CalendarGridProps {
  eventsByDate: Map<string, Event[]>;
  isRange?: boolean;
}

const CalendarGridComponent = ({ eventsByDate, isRange = false }: CalendarGridProps) => {
  const now = today(getLocalTimeZone());

  return (
    <CalendarGridRac>
      <CalendarGridHeaderRac>
        {(day) => (
          <CalendarHeaderCellRac className="size-9 p-0 text-[10px] font-bold uppercase tracking-wider text-neutral-500">
            {day}
          </CalendarHeaderCellRac>
        )}
      </CalendarGridHeaderRac>
      <CalendarGridBodyRac className="[&_td]:px-0">
        {(date) => {
          const dateKey = `${date.year}-${String(date.month).padStart(2, "0")}-${String(date.day).padStart(2, "0")}`;
          const dayEvents = eventsByDate.get(dateKey) || [];
          const dotColors = [...new Set(dayEvents.map((e) => getCategoryDotColor(e.category)))].slice(0, 3);
          const hasEvents = dayEvents.length > 0;
          const isToday = date.compare(now) === 0;

          return (
            <CalendarCellRac
              date={date}
              className={cn(
                "relative flex flex-col items-center justify-center w-9 min-h-9 rounded-xl border border-transparent p-0 text-sm font-normal text-neutral-300 outline-none duration-150 [transition-property:color,background-color,border-radius,box-shadow] data-[disabled]:pointer-events-none data-[unavailable]:pointer-events-none data-[focus-visible]:z-10 data-[hovered]:bg-white/8 data-[selected]:bg-blue-500 data-[hovered]:text-neutral-100 data-[selected]:text-white data-[outside-month]:opacity-30 data-[disabled]:opacity-30 data-[unavailable]:opacity-30 data-[unavailable]:line-through data-[focus-visible]:ring-1 data-[focus-visible]:ring-blue-400",
                isToday && "bg-red-500/20 border-red-500/30 text-red-300 data-[selected]:bg-blue-500 data-[selected]:text-white",
                isRange &&
                  "data-[selected]:rounded-none data-[selection-end]:rounded-e-xl data-[selection-start]:rounded-s-xl data-[selected]:bg-blue-500/20 data-[selected]:text-blue-300 data-[selection-end]:[&:not([data-hover])]:bg-blue-500 data-[selection-start]:[&:not([data-hover])]:bg-blue-500 data-[selection-end]:[&:not([data-hover])]:text-white data-[selection-start]:[&:not([data-hover])]:text-white"
              )}
            >
              {({ defaultChildren }) => (
                <>
                  <span className={cn("relative z-10 leading-none font-bold text-sm", isToday && "text-red-300")}>
                    {defaultChildren}
                  </span>
                  {hasEvents ? (
                    <div className="flex items-center gap-0.5 mt-0.5 h-1.5">
                      {dotColors.map((color, i) => (
                        <span key={i} className={`w-1.5 h-1.5 rounded-full ${color}`} />
                      ))}
                    </div>
                  ) : (
                    <div className="h-1.5 mt-0.5" />
                  )}
                </>
              )}
            </CalendarCellRac>
          );
        }}
      </CalendarGridBodyRac>
    </CalendarGridRac>
  );
};

/* ── Calendar (single/multi) ── */
const Calendar = ({ className, events = [], ...props }: CalendarProps) => {
  const eventsByDate = useMemo(() => {
    const map = new Map<string, Event[]>();
    events.forEach((ev) => {
      const d = new Date(ev.date);
      if (isNaN(d.getTime())) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(ev);
    });
    return map;
  }, [events]);

  return (
    <CalendarRac
      {...props}
      className={composeRenderProps(className, (className) => cn("w-full", className))}
    >
      <CalendarHeader />
      <CalendarGridComponent eventsByDate={eventsByDate} />
    </CalendarRac>
  );
};

/* ── RangeCalendar ── */
const RangeCalendar = ({ className, events = [], ...props }: RangeCalendarProps) => {
  const eventsByDate = useMemo(() => {
    const map = new Map<string, Event[]>();
    events.forEach((ev) => {
      const d = new Date(ev.date);
      if (isNaN(d.getTime())) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(ev);
    });
    return map;
  }, [events]);

  return (
    <RangeCalendarRac
      {...props}
      className={composeRenderProps(className, (className) => cn("w-full", className))}
    >
      <CalendarHeader />
      <CalendarGridComponent eventsByDate={eventsByDate} isRange />
    </RangeCalendarRac>
  );
};

export { Calendar, RangeCalendar };
export type { CalendarProps, RangeCalendarProps };
