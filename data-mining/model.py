from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
    ExtraTreesRegressor,
    VotingRegressor,
)

SEED = 42

gb_params = {
    "learning_rate": 0.1,
    "max_depth": 7,
    "n_estimators": 200,
    "subsample": 0.8,
}

rf_params = {
    "max_depth": None,
    "max_features": 0.5,
    "min_samples_split": 2,
    "n_estimators": 200,
}

et_params = {
    "max_depth": None,
    "max_features": 0.5,
    "min_samples_split": 5,
    "n_estimators": 200,
}


def build_model() -> VotingRegressor:
    """Retorna o ensemble VotingRegressor com os melhores hiperparâmetros."""
    return VotingRegressor(
        estimators=[
            ("extra_trees", ExtraTreesRegressor(**et_params, random_state=SEED, n_jobs=-1)),
            ("grad_bst", GradientBoostingRegressor(**gb_params, random_state=SEED)),
            ("rand_fst", RandomForestRegressor(**rf_params, random_state=SEED, n_jobs=-1)),
        ]
    )
