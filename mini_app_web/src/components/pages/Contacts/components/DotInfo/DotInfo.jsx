import styles from "./DotInfo.module.css";


const DotInfo = ({name}) => {
    return (
        <>
            <div className={styles.wrapper}>
                <p>{name}</p>
            </div>
        </>
    );
}

export {DotInfo};