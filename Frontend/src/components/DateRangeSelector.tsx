import React, { useState, useEffect } from "react";
import { format, isValid, parseISO } from "date-fns";

export interface DateRangeSelectorProps {
  onDateRangeChange?: (startDate: Date | null, endDate: Date | null) => void;
  initialStartDate?: Date;
  initialEndDate?: Date;
  className?: string;
}

export const DateRangeSelector: React.FC<DateRangeSelectorProps> = ({
  onDateRangeChange,
  initialStartDate,
  initialEndDate,
  className = "",
}) => {
  const [startDate, setStartDate] = useState<string>(
    initialStartDate ? format(initialStartDate, "yyyy-MM-dd") : ""
  );
  const [endDate, setEndDate] = useState<string>(
    initialEndDate ? format(initialEndDate, "yyyy-MM-dd") : ""
  );

  // Update local state when initial dates change
  useEffect(() => {
    setStartDate(
      initialStartDate ? format(initialStartDate, "yyyy-MM-dd") : ""
    );
    setEndDate(initialEndDate ? format(initialEndDate, "yyyy-MM-dd") : "");
  }, [initialStartDate, initialEndDate]);

  const handleDateChange = (newStartDate: string, newEndDate: string) => {
    const parsedStartDate = newStartDate ? parseISO(newStartDate) : null;
    const parsedEndDate = newEndDate ? parseISO(newEndDate) : null;

    const validStartDate =
      parsedStartDate && isValid(parsedStartDate) ? parsedStartDate : null;
    const validEndDate =
      parsedEndDate && isValid(parsedEndDate) ? parsedEndDate : null;

    // Ensure start date is not after end date
    if (validStartDate && validEndDate && validStartDate > validEndDate) {
      setStartDate(format(validEndDate, "yyyy-MM-dd"));
      setEndDate(format(validStartDate, "yyyy-MM-dd"));
      onDateRangeChange?.(validEndDate, validStartDate);
    } else {
      onDateRangeChange?.(validStartDate, validEndDate);
    }
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newStartDate = e.target.value;
    setStartDate(newStartDate);
    handleDateChange(newStartDate, endDate);
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEndDate = e.target.value;
    setEndDate(newEndDate);
    handleDateChange(startDate, newEndDate);
  };

  const clearDates = () => {
    setStartDate("");
    setEndDate("");
    onDateRangeChange?.(null, null);
  };

  const setLast7Days = () => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 7);

    const startStr = format(start, "yyyy-MM-dd");
    const endStr = format(end, "yyyy-MM-dd");

    setStartDate(startStr);
    setEndDate(endStr);
    onDateRangeChange?.(start, end);
  };

  const setLast30Days = () => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 30);

    const startStr = format(start, "yyyy-MM-dd");
    const endStr = format(end, "yyyy-MM-dd");

    setStartDate(startStr);
    setEndDate(endStr);
    onDateRangeChange?.(start, end);
  };

  return (
    <div className={className}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="start-date"
              className="block text-xs text-gray-400 font-medium mb-1"
            >
              From
            </label>
            <input
              type="date"
              id="start-date"
              value={startDate}
              onChange={handleStartDateChange}
              className="filter-input w-full px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-mountain-meadow focus:ring-opacity-50"
            />
          </div>

          <div>
            <label
              htmlFor="end-date"
              className="block text-xs text-gray-400 font-medium mb-1"
            >
              To
            </label>
            <input
              type="date"
              id="end-date"
              value={endDate}
              onChange={handleEndDateChange}
              className="filter-input w-full px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-mountain-meadow focus:ring-opacity-50"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={clearDates}
            className="px-2 py-1 text-xs border border-stone text-stone hover:bg-stone hover:text-dark-green rounded-md transition-colors font-medium"
          >
            Clear
          </button>
          <button
            onClick={setLast7Days}
            className="px-2 py-1 text-xs bg-bangladesh-green hover:bg-mountain-meadow text-white hover:text-dark-green rounded-md transition-colors font-medium"
          >
            7 Days
          </button>
          <button
            onClick={setLast30Days}
            className="px-2 py-1 text-xs bg-bangladesh-green hover:bg-mountain-meadow text-white hover:text-dark-green rounded-md transition-colors font-medium"
          >
            30 Days
          </button>
        </div>
      </div>
    </div>
  );
};
