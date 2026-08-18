const ArticlesSvg = ({className}) => {
    return (
        <>
            <svg
            className={className}
            viewBox="0 0 24 24"
            fill="none"
            >
                <path d="M5 3h10l4 4v14H5V3z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                <path d="M9 10h6M9 14h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
        </>
    );
};

export {ArticlesSvg}