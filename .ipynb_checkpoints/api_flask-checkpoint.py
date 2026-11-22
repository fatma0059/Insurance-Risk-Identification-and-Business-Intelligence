
from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import joblib
import json
from datetime import datetime
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_pinball_loss
from xgboost import XGBRegressor
import os

app = Flask(__name__)


class QuantileEnsemble:
    def __init__(self, quantiles=[0.1, 0.5, 0.9]):
        self.quantiles = quantiles
        self.modeles = {}

    def predict(self, X):
        predictions = {}
        for q, modele in self.modeles.items():
            predictions[f'q{int(q*100)}'] = modele.predict(X)
        return predictions

    def predict_interval(self, X):
        predictions = self.predict(X)
        return {
            'lower': predictions['q10'],
            'median': predictions['q50'],
            'upper': predictions['q90'],
            'interval_width': predictions['q90'] - predictions['q10']
        }

MODEL_DIR = "models"

def charger_modeles():
    """Charge tous les modèles nécessaires pour l'API"""
    try:
        model_triage = joblib.load(f'{MODEL_DIR}/xgboost_triage.pkl')
        model_quantile = joblib.load(f'{MODEL_DIR}/quantile_ensemble.pkl')
        preprocessor = joblib.load(f'{MODEL_DIR}/preprocesseur.pkl')

        with open(f'{MODEL_DIR}/metadata.json', 'r') as f:
            metadata = json.load(f)

        print(" Tous les modèles chargés avec succès")
        return model_triage, model_quantile, preprocessor, metadata
    except Exception as e:
        print(f" Erreur lors du chargement : {e}")
        return None, None, None, None

model_triage, model_quantile, preprocessor, metadata = charger_modeles()

@app.route('/')
def home():
    return jsonify({
        'service': 'Assurance Triage API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            '/': 'GET - Information du service',
            '/health': 'GET - État du service',
            '/metadata': 'GET - Métadonnées des modèles',
            '/predict': 'POST - Prédiction de la complexité',
            '/predict_cost': 'POST - Prédiction du coût',
            '/predict_full': 'POST - Prédiction complète'
        }
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy' if model_triage is not None else 'unhealthy',
        'timestamp': datetime.now().isoformat(),
        'models_loaded': model_triage is not None
    })

@app.route('/metadata')
def get_metadata():
    if metadata is None:
        return jsonify({'error': 'Métadonnées non disponibles'}), 503
    return jsonify(metadata)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        if model_triage is None:
            return jsonify({'error': 'Modèle non chargé'}), 503

        data = request.get_json()
        required_fields = metadata.get('features_numeriques', []) + metadata.get('features_categoriques', [])
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Champs manquants : {missing}'}), 400

        df = pd.DataFrame([data])
        X_processed = preprocessor.transform(df)
        pred = model_triage.predict(X_processed)[0]
        proba = model_triage.predict_proba(X_processed)[0]

        return jsonify({
            'prediction': 'Complexe' if pred == 1 else 'Simple',
            'probabilite_simple': float(proba[0]),
            'probabilite_complexe': float(proba[1]),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/predict_cost', methods=['POST'])
def predict_cost():
    try:
        if model_quantile is None:
            return jsonify({'error': 'Modèle quantile non chargé'}), 503

        data = request.get_json()
        required_fields = metadata.get('features_numeriques', []) + metadata.get('features_categoriques', [])
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Champs manquants : {missing}'}), 400

        df = pd.DataFrame([data])
        X_processed = preprocessor.transform(df)
        pred = model_quantile.predict(X_processed)

        return jsonify({
            'cost_lower_10': float(pred['q10'][0]),
            'cost_median_50': float(pred['q50'][0]),
            'cost_upper_90': float(pred['q90'][0]),
            'intervalle': f"[{pred['q10'][0]:.0f} - {pred['q90'][0]:.0f}]",
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/predict_full', methods=['POST'])
def predict_full():
    try:
        if model_triage is None or model_quantile is None:
            return jsonify({'error': 'Modèles non chargés'}), 503

        data = request.get_json()
        required_fields = metadata.get('features_numeriques', []) + metadata.get('features_categoriques', [])
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Champs manquants : {missing}'}), 400

        df = pd.DataFrame([data])
        X_processed = preprocessor.transform(df)

        pred_triage = model_triage.predict(X_processed)[0]
        proba_triage = model_triage.predict_proba(X_processed)[0]
        pred_cost = model_quantile.predict(X_processed)

        return jsonify({
            'triage': {
                'prediction': 'Complexe' if pred_triage == 1 else 'Simple',
                'probabilite_simple': float(proba_triage[0]),
                'probabilite_complexe': float(proba_triage[1])
            },
            'cout': {
                'lower_10': float(pred_cost['q10'][0]),
                'median_50': float(pred_cost['q50'][0]),
                'upper_90': float(pred_cost['q90'][0])
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
