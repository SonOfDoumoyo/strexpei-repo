import { useState, useEffect } from "react";

export default function useTimeOfDay () {
    const getTimeOfDay = () => {
        const hour = new Date().getHours();

        if (hour >= 5 && hour < 12) return "Morning";
        if (hour >= 12 && hour < 17) return "Afternoon";
        if (hour >= 17 && hour < 21) return "Evening";
        return "Night";
    }

    const [timeOfDay, setTimeOfDay] = useState(getTimeOfDay);

    useEffect(() => {
        const interval = setInterval(() => {
            setTimeOfDay(getTimeOfDay);
        }, 60 * 1000);

        return () => clearInterval(interval)
    }, [])

    return timeOfDay;
}