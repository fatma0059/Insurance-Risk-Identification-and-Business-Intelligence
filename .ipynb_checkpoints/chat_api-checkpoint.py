from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import pymysql
import pymysql.cursors
from datetime import datetime

app = Flask(__name__)
CORS(app)

PREDICTION_API_URL = "http://localhost:5000"

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'astre_dw',
    'port': 3306,
    'charset': 'utf8mb4'
}


def get_connection():
    """Établit la connexion à la base de données MySQL/MariaDB."""
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'],
            charset=DB_CONFIG['charset'],
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✅ Connexion DB réussie !")
        return conn
    except pymysql.err.OperationalError as e:
        if e.args[0] == 2003:
            print("❌ MySQL n'est pas démarré ! Lancez XAMPP/WAMP/MAMP")
        else:
            print(f"❌ Erreur de connexion DB : {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur de connexion DB : {e}")
        return None


def search_client_candidates(identifier):
    """Recherche un client par Client_ID, Nom ou Prénom."""
    if not identifier:
        return []
    
    identifier = identifier.strip()
    conn = get_connection()
    if not conn:
        print("❌ Connexion DB impossible")
        return []

    try:
        with conn.cursor() as cursor:
            search_term = f"%{identifier}%"
            
            # Recherche dans Client_ID, Nom ET Prenom
            cursor.execute("""
                SELECT id_pk, Nom, Prenom, Client_ID, Categorie_Risque
                FROM dim_clients
                WHERE TRIM(Client_ID) LIKE %s
                OR TRIM(Nom) LIKE %s
                OR TRIM(Prenom) LIKE %s
                OR CONCAT(TRIM(Nom), ' ', TRIM(Prenom)) LIKE %s
                OR CONCAT(TRIM(Prenom), ' ', TRIM(Nom)) LIKE %s
                LIMIT 10
            """, (search_term, search_term, search_term, search_term, search_term))
            
            results = cursor.fetchall()
            
            print(f"🔍 Recherche '{identifier}' → {len(results)} résultat(s)")
            for r in results:
                print(f"   - {r['Client_ID']} | {r['Nom']} {r.get('Prenom', '')}")
            
            return results
            
    except Exception as e:
        print(f"❌ Erreur lors de la recherche client : {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        conn.close()


def get_client_features(id_pk):
    """Récupère les données d'un client avec la bonne jointure."""
    conn = get_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            # 1. Récupérer le client
            cursor.execute("""
                SELECT id_pk, Client_ID, Nom, Prenom, Age, 
                       Categorie_Risque, Risque_Comportemental, Risque_Fraude
                FROM dim_clients
                WHERE id_pk = %s
            """, (id_pk,))
            client = cursor.fetchone()
            
            if not client:
                print(f"❌ Client avec id_pk={id_pk} non trouvé")
                return None
            
            print(f"✅ Client trouvé : {client['Client_ID']} - {client['Nom']} {client.get('Prenom', '')}")
            
            # 2. Récupérer la police dans fact_polass (corrigé)
            cursor.execute("""
                SELECT Contract_ID, Type_Couverture, Nb_Sinistres_Precedents,
                       Delai_Souscription_Sinistre_Jours
                FROM fact_polass
                WHERE clientID = %s
                ORDER BY Date_Debut_Contrat DESC
                LIMIT 1
            """, (client['id_pk'],))
            police = cursor.fetchone()
            
            print(f"🔍 Police trouvée : {police is not None}")
            if police:
                print(f"   Contract_ID: {police.get('Contract_ID')}")
            
            # 3. Récupérer le véhicule
            vehicule = None
            if police and police.get('Contract_ID'):
                cursor.execute("""
                    SELECT Type_Vehicule, Annee_Modele, Puissance_Fiscale,
                           Kilometrage_Actuel, Valeur_Vehicule, Usage_Vehicule
                    FROM dim_vehicules
                    WHERE Contract_ID = %s
                """, (police['Contract_ID'],))
                vehicule = cursor.fetchone()
                print(f"🔍 Véhicule trouvé : {vehicule is not None}")
            
            # 4. Construire les features
            features = {
                "Age": client.get("Age") or 45,
                "Categorie_Risque": client.get("Categorie_Risque") or "Moyen",
                "Risque_Comportemental": client.get("Risque_Comportemental") or 0.3,
                "Risque_Fraude": client.get("Risque_Fraude") or 0.1,
                "Nb_Sinistres_Precedents": police.get("Nb_Sinistres_Precedents") if police else 0,
                "Delai_Souscription_Sinistre_Jours": police.get("Delai_Souscription_Sinistre_Jours") if police else 365,
                "Type_Couverture": police.get("Type_Couverture") if police else "Tous risques",
                "Type_Vehicule": vehicule.get("Type_Vehicule") if vehicule else "Berline",
                "Annee_Modele": vehicule.get("Annee_Modele") if vehicule else 2018,
                "Puissance_Fiscale": vehicule.get("Puissance_Fiscale") if vehicule else 5,
                "Kilometrage_Actuel": vehicule.get("Kilometrage_Actuel") if vehicule else 50000,
                "Valeur_Vehicule": vehicule.get("Valeur_Vehicule") if vehicule else 15000,
                "Usage_Vehicule": vehicule.get("Usage_Vehicule") if vehicule else "Particulier",
                "Type_Sinistre_Claim": "Accident",
            }
            
            client_display = {
                "Client_ID": client["Client_ID"],
                "Nom": client["Nom"] or "Inconnu",
                "Prenom": client["Prenom"] or ""
            }
            
            print(f"✅ Données récupérées pour {client['Nom']}")
            return {"features": features, "client": client_display}
            
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données client : {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()


def extract_client_reference(user_message, payload_data):
    """
    Détermine si le message concerne un client précis.
    """
    if payload_data.get('client_id'):
        return payload_data['client_id']
    if payload_data.get('client_name'):
        return payload_data['client_name']

    match = re.search(r'CLI-[A-Z0-9]{6,}', user_message, re.IGNORECASE)
    if match:
        return match.group(0)

    return None


def detect_intent(message):
    message = message.lower()

    if any(word in message for word in ['coût', 'cout', 'prix', 'estimation', 'combien', '€', 'euro']):
        return 'cost'
    elif any(word in message for word in ['complexe', 'simple', 'triage', 'classer', 'catégorie', 'type']):
        return 'triage'
    elif any(word in message for word in ['bonjour', 'salut', 'hello', 'coucou', 'hey']):
        return 'greeting'
    elif any(word in message for word in ['merci', 'thanks', 'ok', 'd\'accord']):
        return 'thanks'
    elif any(word in message for word in ['aide', 'help', 'que faire', 'comment']):
        return 'help'
    else:
        return 'unknown'


def extract_sinistre_data(user_message, default_data):
    data = default_data.copy()

    montant_match = re.search(r'(\d+)\s*€', user_message)
    if montant_match:
        data['Valeur_Vehicule'] = float(montant_match.group(1))

    age_match = re.search(r'âge\s*(\d+)', user_message, re.IGNORECASE)
    if age_match:
        data['Age'] = int(age_match.group(1))

    return data


DEFAULT_SINISTRE = {
    "Nb_Sinistres_Precedents": 1,
    "Delai_Souscription_Sinistre_Jours": 365,
    "Age": 45,
    "Risque_Comportemental": 0.3,
    "Risque_Fraude": 0.1,
    "Annee_Modele": 2018,
    "Puissance_Fiscale": 5,
    "Kilometrage_Actuel": 50000,
    "Valeur_Vehicule": 15000,
    "Type_Sinistre_Claim": "Accident",
    "Type_Couverture": "Tous risques",
    "Categorie_Risque": "Moyen",
    "Type_Vehicule": "Berline",
    "Usage_Vehicule": "Particulier"
}


@app.route('/')
def home():
    return jsonify({
        'service': 'Chat Assistant Assurance',
        'version': '2.0.0',
        'status': 'running',
        'endpoints': {
            '/': 'Information',
            '/health': 'État du service',
            '/chat': 'POST - Envoyer un message',
            '/client/search': 'GET - Rechercher un client',
            '/debug/db': 'GET - Diagnostic base de données',
            '/debug/full/<id_pk>': 'GET - Diagnostic complet client'
        }
    })


@app.route('/health')
def health():
    try:
        response = requests.get(f'{PREDICTION_API_URL}/health', timeout=2)
        prediction_status = response.status_code == 200
    except Exception:
        prediction_status = False

    db_ok = get_connection() is not None

    return jsonify({
        'status': 'healthy',
        'prediction_api_available': prediction_status,
        'database_available': db_ok,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/client/search')
def client_search():
    q = request.args.get('q', '')
    if not q:
        return jsonify({'error': "Paramètre 'q' manquant"}), 400
    candidates = search_client_candidates(q)
    return jsonify({'query': q, 'count': len(candidates), 'results': candidates})


@app.route('/debug/db')
def debug_db():
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Connexion DB échouée'}), 500
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM dim_clients")
            total = cursor.fetchone()
            
            cursor.execute("""
                SELECT id_pk, Nom, Prenom, Client_ID, Categorie_Risque 
                FROM dim_clients 
                LIMIT 10
            """)
            clients = cursor.fetchall()
            
            return jsonify({
                'database': DB_CONFIG['database'],
                'total_clients': total['total'],
                'sample_clients': clients
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/debug/full/<int:id_pk>')
def debug_full(id_pk):
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Connexion DB impossible'}), 500
    
    try:
        with conn.cursor() as cursor:
            result = {}
            
            cursor.execute("SELECT * FROM dim_clients WHERE id_pk = %s", (id_pk,))
            result['client'] = cursor.fetchone()
            
            if result['client']:
                client_id = result['client']['id_pk']
                
                cursor.execute("""
                    SELECT * FROM fact_polass WHERE clientID = %s
                """, (client_id,))
                result['polices'] = cursor.fetchall()
                result['polices_count'] = len(result['polices'])
                
                if result['polices']:
                    contract_ids = [p['Contract_ID'] for p in result['polices']]
                    placeholders = ','.join(['%s'] * len(contract_ids))
                    cursor.execute(f"""
                        SELECT * FROM dim_vehicules 
                        WHERE Contract_ID IN ({placeholders})
                    """, contract_ids)
                    result['vehicules'] = cursor.fetchall()
                    result['vehicules_count'] = len(result['vehicules'])
            
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        sinistre_data_input = data.get('sinistre_data', {})
        conversation_id = data.get('conversation_id', 'default')

        client_info = None
        client_ref = extract_client_reference(user_message, data)

        if client_ref:
            candidates = search_client_candidates(client_ref)

            if len(candidates) == 0:
                return jsonify({
                    'response': f"❌ Aucun client trouvé pour « {client_ref} ». Vérifiez le nom ou le Client_ID.",
                    'type': 'client_not_found',
                    'intent': 'client_not_found'
                })

            if len(candidates) > 1:
                return jsonify({
                    'response': f"🔍 Plusieurs clients correspondent à « {client_ref} ». Merci de préciser lequel.",
                    'type': 'client_disambiguation',
                    'intent': 'client_disambiguation',
                    'candidates': candidates
                })

            chosen = candidates[0]
            full_data = get_client_features(chosen['id_pk'])
            if full_data is None:
                return jsonify({
                    'response': "❌ Client trouvé mais impossible de récupérer ses données complètes. Vérifiez que la table fact_polass contient des données pour ce client.",
                    'type': 'error',
                    'intent': 'error'
                })

            client_info = full_data['client']
            sinistre_data = full_data['features']
            sinistre_data = extract_sinistre_data(user_message, sinistre_data)

        else:
            sinistre_data = sinistre_data_input if sinistre_data_input else {}
            for key, value in DEFAULT_SINISTRE.items():
                sinistre_data.setdefault(key, value)
            sinistre_data = extract_sinistre_data(user_message, sinistre_data)

        intent = detect_intent(user_message)

        if intent == 'cost':
            return handle_cost(sinistre_data, client_info)
        elif intent == 'triage':
            return handle_triage(sinistre_data, client_info)
        elif intent == 'greeting':
            return handle_greeting()
        elif intent == 'thanks':
            return handle_thanks()
        elif intent == 'help':
            return handle_help()
        else:
            return handle_unknown(user_message)

    except Exception as e:
        print(f"❌ Erreur dans /chat : {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'response': f"❌ Désolé, une erreur s'est produite : {str(e)}",
            'type': 'error',
            'intent': 'error'
        }), 500


def _client_label(client_info):
    if not client_info:
        return ""
    return f" pour **{client_info['Nom']} {client_info['Prenom']}** ({client_info['Client_ID']})"


def handle_cost(sinistre_data, client_info=None):
    try:
        response = requests.post(
            f'{PREDICTION_API_URL}/predict_cost',
            json=sinistre_data,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()

            return jsonify({
                'response': f"""📊 **Estimation du coût{_client_label(client_info)}**

💰 **Coût médian :** {result['cost_median_50']:.0f} €
📈 **Intervalle :** {result['cost_lower_10']:.0f} € - {result['cost_upper_90']:.0f} €

*📌 Ces estimations sont basées sur {'les données réelles du client' if client_info else 'les données fournies'}.*""",
                'type': 'cost',
                'intent': 'cost',
                'client': client_info,
                'data': {
                    'lower': result['cost_lower_10'],
                    'median': result['cost_median_50'],
                    'upper': result['cost_upper_90']
                }
            })
        else:
            return jsonify({
                'response': "❌ Je n'ai pas pu obtenir l'estimation du coût. Le service de prédiction est peut-être indisponible.",
                'type': 'error',
                'intent': 'error'
            })

    except requests.exceptions.ConnectionError:
        return jsonify({
            'response': "❌ Je n'arrive pas à contacter le service de prédiction. Vérifiez que l'API principale est bien lancée sur le port 5000.",
            'type': 'error',
            'intent': 'error'
        })
    except Exception as e:
        return jsonify({
            'response': f"❌ Erreur lors de l'estimation du coût : {str(e)}",
            'type': 'error',
            'intent': 'error'
        })


def handle_triage(sinistre_data, client_info=None):
    try:
        response = requests.post(
            f'{PREDICTION_API_URL}/predict',
            json=sinistre_data,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()

            prediction = result['prediction']
            proba_simple = result['probabilite_simple'] * 100
            proba_complexe = result['probabilite_complexe'] * 100

            emoji = "⚠️" if prediction == "Complexe" else "✅"

            return jsonify({
                'response': f"""{emoji} **Analyse du sinistre{_client_label(client_info)}**

📋 **Classification :** **{prediction}**
📊 **Probabilités :**
• Simple : {proba_simple:.1f}%
• Complexe : {proba_complexe:.1f}%

*📌 Cette classification est basée sur {'les données réelles du client' if client_info else 'les données fournies'}.*""",
                'type': 'triage',
                'intent': 'triage',
                'client': client_info,
                'data': {
                    'prediction': prediction,
                    'probabilite_simple': proba_simple,
                    'probabilite_complexe': proba_complexe
                }
            })
        else:
            return jsonify({
                'response': "❌ Je n'ai pas pu analyser le sinistre. Le service de prédiction est peut-être indisponible.",
                'type': 'error',
                'intent': 'error'
            })

    except requests.exceptions.ConnectionError:
        return jsonify({
            'response': "❌ Je n'arrive pas à contacter le service de prédiction. Vérifiez que l'API principale est bien lancée sur le port 5000.",
            'type': 'error',
            'intent': 'error'
        })
    except Exception as e:
        return jsonify({
            'response': f"❌ Erreur lors de l'analyse : {str(e)}",
            'type': 'error',
            'intent': 'error'
        })


def handle_greeting():
    return jsonify({
        'response': """👋 **Bonjour !**

Je suis votre **assistant assurance** 🤖

Je peux vous aider avec :
• 💰 **Coût** : demandez "quel est le coût ?" ou "combien ça coûte ?"
• 📋 **Triage** : demandez "ce sinistre est-il complexe ?" ou "est-ce simple ?"
• 🔍 **Recherche client** : indiquez un Client_ID (ex: CLI-21288B8C)

Que puis-je faire pour vous ?""",
        'type': 'greeting',
        'intent': 'greeting'
    })


def handle_thanks():
    return jsonify({
        'response': """🙏 **Avec plaisir !**

N'hésitez pas si vous avez d'autres questions.

💡 Pour rappel, je peux vous aider avec :
• Estimation des coûts
• Classification des sinistres
• Recherche client (par nom ou Client_ID)

À bientôt ! 😊""",
        'type': 'thanks',
        'intent': 'thanks'
    })


def handle_help():
    return jsonify({
        'response': """❓ **Aide - Assistant Assurance**

Voici ce que je peux faire pour vous :

💰 **Estimation des coûts**
Exemple : "quel est le coût de ce sinistre ?"

📋 **Classification des sinistres**
Exemple : "ce sinistre est-il complexe ?"

🔍 **Recherche client**
Indiquez un Client_ID dans votre message (ex: "coût pour CLI-21288B8C")

👋 **Général**
Exemple : "bonjour", "merci", "aide"

Que voulez-vous faire ?""",
        'type': 'help',
        'intent': 'help'
    })


def handle_unknown(message):
    return jsonify({
        'response': f"""🤔 **Je n'ai pas bien compris votre demande.**

Vous avez dit : *"{message}"*

💡 **Je peux vous aider avec :**
• 💰 **Coût** : demandez "quel est le coût ?"
• 📋 **Triage** : demandez "ce sinistre est-il complexe ?"
• ❓ **Aide** : demandez "aide"

Essayez de reformuler votre demande. 😊""",
        'type': 'unknown',
        'intent': 'unknown'
    })


if __name__ == '__main__':
    print("🚀 CHAT API DÉMARRÉ")
    print("📡 Chat API : http://localhost:5001")
    print(f"🔗 Prédiction API : {PREDICTION_API_URL}")
    print(f"🗄️ Base de données : {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print("=" * 50)
    print("Appuyez sur Ctrl+C pour arrêter")
    app.run(host='0.0.0.0', port=5001, debug=False)