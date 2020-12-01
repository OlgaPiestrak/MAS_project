<?php
use Slim\App;
use Slim\Http\Request;
use Slim\Http\Response;
use controllers\HomeController;

return function (App $app) {
    $app->get('/', HomeController::class . ':home');
    $app->get('/devices', HomeController::class . ':get_devices');
    $app->post('/devices', HomeController::class . ':set_devices');
    $app->post('/start_feed', HomeController::class . ':start_feed');
    $app->post('/stop_feed', HomeController::class . ':stop_feed');
    $app->post('/command', HomeController::class . ':command');
    $app->post('/signup', HomeController::class . ':signup');
};
