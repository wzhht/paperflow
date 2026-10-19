from paperflow.models import (
    Publisher,
    Route,
    RouteDecision,
)
from paperflow.utils.doi import normalize_doi


def route_doi(value: str) -> RouteDecision:
    """
    Keep original structured routes first, then explicit additional PDF routes.
    A supported route is not a guarantee of subscription access.
    Unknown prefixes still require the separate local parse-pdf command.
    """

    doi = normalize_doi(value)

    if doi.startswith("10.1016/"):
        return RouteDecision(
            doi=doi,
            publisher=Publisher.ELSEVIER,
            route=Route.ELSEVIER,
            supported=True,
            reason="Elsevier DOI supported by PaperFlow V2.",
        )

    if doi.startswith("10.1007/s12273"):
        return RouteDecision(
            doi=doi,
            publisher=Publisher.SPRINGER_NATURE,
            route=Route.BUILDING_SIMULATION,
            supported=True,
            reason=("Building Simulation DOI supported by PaperFlow V2."),
        )

    if doi.startswith("10.1038/"):
        return RouteDecision(
            doi=doi,
            publisher=Publisher.SPRINGER_NATURE,
            route=Route.NATURE,
            supported=True,
            reason=("Nature Portfolio DOI supported by PaperFlow V2."),
        )

    if doi.startswith(("10.1007/", "10.1186/")):
        return RouteDecision(
            doi,
            Publisher.SPRINGER_NATURE,
            Route.SPRINGER,
            True,
            "Springer JATS or authorized/public PDF route.",
        )
    if doi.startswith("10.1109/"):
        return RouteDecision(
            doi,
            Publisher.IEEE,
            Route.IEEE,
            True,
            "IEEE metadata and authorized/public PDF route; includes CVPR.",
        )
    if doi.startswith("10.48550/arxiv."):
        return RouteDecision(doi, Publisher.ARXIV, Route.ARXIV, True, "arXiv public PDF route.")
    if doi.startswith(
        (
            "10.1145/",
            "10.5194/",
            "10.1002/",
            "10.1111/",
            "10.1080/",
            "10.1093/",
            "10.3389/",
            "10.1371/",
            "10.3390/",
            "10.1103/",
            "10.1126/",
            "10.7554/", "10.1101/", "10.2139/", "10.26434/",
            "10.1021/", "10.1039/", "10.1088/", "10.1063/", "10.1115/",
            "10.1177/", "10.1017/", "10.1086/", "10.1515/", "10.1142/",
            "10.2514/", "10.1146/", "10.1128/", "10.1155/", "10.1159/",
            "10.1089/", "10.1108/", "10.1504/", "10.3233/", "10.1096/",
            "10.1242/", "10.26508/", "10.15252/", "10.1094/", "10.1113/",
            "10.1056/", "10.1136/", "10.1210/", "10.1530/", "10.1124/",
            "10.1172/", "10.1182/", "10.2337/", "10.1590/", "10.3892/",
            "10.3109/", "10.1037/", "10.1158/", "10.1097/", "10.1249/",
            "10.1001/", "10.2307/", "10.1161/", "10.1167/", "10.1083/",
            "10.1143/", "10.1073/", "10.1055/", "10.1061/", "10.1152/",
            "10.2478/", "10.1137/", "10.1116/", "10.1149/", "10.1364/",
            "10.3938/", "10.3762/", "10.31635/", "10.2174/", "10.1042/",
            "10.1147/", "10.1353/", "10.2105/", "10.1513/", "10.34763/",
            "10.2147/", "10.20892/",
        )
    ):
        return RouteDecision(
            doi,
            Publisher.OTHER,
            Route.PUBLIC_PDF,
            True,
            "Open/authorized PDF or local PDF; no guaranteed paid access.",
        )

    return RouteDecision(
        doi=doi,
        publisher=Publisher.UNKNOWN,
        route=Route.UNSUPPORTED,
        supported=False,
        reason=("No PaperFlow V2 route exists for this DOI."),
    )
