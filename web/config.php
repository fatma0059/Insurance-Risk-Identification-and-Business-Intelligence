<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Configuration de la base de données
define('DB_HOST', 'localhost');
define('DB_NAME', 'astre_dw');
define('DB_USER', 'root');
define('DB_PASS', '');

// Connexion à la base de données
function getDBConnection() {
    try {
        $pdo = new PDO(
            "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
            DB_USER,
            DB_PASS
        );
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        return $pdo;
    } catch(PDOException $e) {
        http_response_code(500);
        echo json_encode([
            'success' => false, 
            'error' => 'Erreur de connexion à la base de données: ' . $e->getMessage()
        ]);
        exit;
    }
}

// Fonction pour exécuter une requête et retourner les résultats
function executeQuery($sql, $params = []) {
    $pdo = getDBConnection();
    try {
        $stmt = $pdo->prepare($sql);
        $stmt->execute($params);
        $data = $stmt->fetchAll();
        return [
            'success' => true,
            'data' => $data,
            'count' => count($data)
        ];
    } catch(PDOException $e) {
        return [
            'success' => false,
            'error' => $e->getMessage()
        ];
    }
}
?>