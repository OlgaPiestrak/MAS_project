<?php
use Slim\App;
use Slim\Http\Request;
use Slim\Http\Response;
use controllers\HomeController;

return function (App $app) {
    $app->get('/', HomeController::class . ':home');
    $app->post('/settings', HomeController::class . ':settings');
    $app->get('/robot_logs', HomeController::class . ':robotLogs');
    $app->post('/robot_disconnect', HomeController::class . ':robotDisconnect');
    $app->post('/signup', HomeController::class . ':signup');
};
