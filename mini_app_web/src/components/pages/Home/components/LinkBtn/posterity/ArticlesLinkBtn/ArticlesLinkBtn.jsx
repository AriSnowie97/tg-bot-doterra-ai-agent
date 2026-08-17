import styles from "./ArticlesLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";

const ArticlesLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/articles"}
            img={""}
            h3Text={"База знань"}
            pText={"Каталог наборів і продуктів з описом складу та застосування"}
            newStyles={styles}/>
        </>
    );
}

export {ArticlesLinkBtn};