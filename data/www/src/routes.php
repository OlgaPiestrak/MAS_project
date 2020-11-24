<?php
use Slim\App;
use Slim\Http\Request;
use Slim\Http\Response;
use controllers\HomeController;

return function (App $app) {
    $app->get('/', HomeController::class . ':home');
    $app->get('/devices', HomeController::class . ':get_devices');
    $app->post('/devices', HomeController::class . ':set_devices');
    $app->post('/signup', HomeController::class . ':signup');
};
