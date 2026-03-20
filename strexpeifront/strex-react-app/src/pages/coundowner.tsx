import { useState, useEffect } from "react";
import "../assets/css/verify.css";


interface ResendCountdownProps {
        onCountdownEnd: () => void;
    }

export const ResendCountdown = ({ onCountdownEnd }: ResendCountdownProps) => {
    const [ seconds, setSeconds ] = useState(600);

    useEffect(() => {
        if (seconds <= 0) {
            onCountdownEnd();
            return;
        }

        const timer = setInterval(() => {
            setSeconds((prev) => prev - 1);
        }, 1000);

        return () => clearInterval(timer);
    }, [seconds]);

    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const display = `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

    return (
        <p className="text-ms text-red-500">Maximum resend attempts reached. Try again in {" "}<span className="font-semibold">{display}</span></p>
    );
}
