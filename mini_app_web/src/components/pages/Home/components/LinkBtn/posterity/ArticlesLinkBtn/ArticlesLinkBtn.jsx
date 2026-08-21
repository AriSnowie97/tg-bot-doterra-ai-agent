import styles from "./ArticlesLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";
import { ArticlesSvg } from "../../../../../../../assets/icons";


const ArticlesLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/articles"}
            Svg={ArticlesSvg}
            h3Text={"База знань"}
            pText={"Каталог наборів і продуктів з описом складу та застосування"}
            newStyles={styles}/>
        </>
    );
}

export {ArticlesLinkBtn};