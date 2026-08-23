import styles from "./NotFound.module.css";
import { useLocation } from "react-router-dom";

const NotFound = () => {
    const location = useLocation();

    return (
        <>
            <div className={styles.wrapper}>
                <p>404 Not Found D;</p>
                <p style={{fontSize: "10px", marginTop: "10px", color: "red"}}>Path: {location.pathname}{location.search}{location.hash}</p>
            </div>
        </>
    );
}

export {NotFound};