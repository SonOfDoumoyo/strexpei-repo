import { useState, useEffect } from "react";

export default function useDateOfDay () {
    const getDateOfDay = () => {
        const date = new Date();
        const days = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday"
        ]

        const months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        return `${days[date.getDay()]}, ` + `${date.getDate()} ` + `${months[date.getMonth()]} ` + `${date.getFullYear()}`;
    }

    const [dateOfDay, setDateOfDay] = useState(getDateOfDay);

    useEffect(() => {
        const interval = setInterval(() => {
            setDateOfDay(getDateOfDay);
        }, 1000);

        return () => clearInterval(interval)
    }, [])

    return dateOfDay;
}