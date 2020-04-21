<?php
use Slim\App;
use Slim\Http\Request;
use Slim\Http\Response;
use controllers\HomeController;

return function (App $app) {
    $app->get('/', HomeController::class . ':home');
    $app->post('/settings', HomeController::class . ':settings');
    $app->post('/service_start', HomeController::class . ':serviceStart');
    $app->post('/service_stop', HomeController::class . ':serviceStop');;
    $app->get('/service_log', HomeController::class . ':serviceLog');
    $app->get('/clear_logs', HomeController::class . ':clearLogs');
    $app->get('/robot_logs', HomeController::class . ':robotLogs');
};
