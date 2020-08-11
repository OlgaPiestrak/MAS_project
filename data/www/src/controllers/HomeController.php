<?php
namespace controllers;

use Psr\Container\ContainerInterface;
use Slim\Http\Request;
use Slim\Http\Response;

class HomeController
{

    /** @var ContainerInterface */
    protected $container;

    public function __construct(ContainerInterface $container)
    {
        $this->container = $container;
    }

    public function home(Request $request, Response $response, $args)
    {
        return $this->container->get('renderer')->render($response, 'index.phtml', $args);
    }

    public function signup(Request $request, Response $response, $args)
    {
        $params = $request->getParams();
        $username = $params['newUser'] ?? '';
        if (! ctype_alnum($username)) {
            return $response->withStatus(422, 'Please use only alphanumeric characters in the username.');
        }
        if (strlen($username) < 4) {
            return $response->withStatus(422, 'Please use at least 4 characters in the username.');
        }
        $password = $params['newPass'] ?? '';
        if (strlen($password) < 8) {
            return $response->withStatus(422, 'Please use at least 8 characters in the password.');
        }

        $dir = __DIR__;
        echo self::exec("python2 -u $dir/register_user.py --username $username --password $password");
    }

    public function settings(Request $request, Response $response, $args)
    {
        $params = $request->getParams();
        $myIp = $params['myIp'] ?? '';
        $myUser = $params['myUser'] ?? '';
        $myPass = $params['myPass'] ?? '';
        $robotIp = $params['robotIp'] ?? '';
        $robotPass = $params['robotPass'] ?? '';

        // LAN IP-address of user's device (required)
        if (! filter_var($myIp, FILTER_VALIDATE_IP)) {
            return $response->withStatus(422, 'The IP-address for the robot is invalid.');
        }
        $_SESSION['myIp'] = $myIp;
        if (empty($myUser)) {
            return $response->withStatus(422, 'Please give your username.');
        }
        $_SESSION['myUser'] = $myUser;
        if (empty($myPass)) {
            return $response->withStatus(422, 'Please give your password.');
        }
        $_SESSION['myPass'] = $myPass;
        echo "Creating configuration files using the given information...\n";
		$path = '/opt/cbsr';
        echo self::exec("cp -f $path/webserver/html/socket.js.template $path/webserver/html/socket.js && echo \"OK (1/4)\"");
        echo self::exec("sed -i \"s/127.0.0.1/$myIp/\" $path/webserver/html/socket.js && echo \"OK (2/4)\"");
		$path .= '/robot_scripts';
        echo self::exec("cp -f $path/start.sh.template $path/start.sh && echo \"OK (3/4)\"");
        echo self::exec("sed -i -e 's/unknown1/$myIp/' -e 's/unknown2/$myUser/' -e 's/unknown3/$myPass/' $path/start.sh && echo \"OK (4/4)\"");
		self::exec("chmod +x $path/*.sh");

        // LAN IP-address of the Nao/Pepper (if used)
        if (empty($robotIp) || filter_var($robotIp, FILTER_VALIDATE_IP)) {
            $_SESSION['robotIp'] = $robotIp;
        } else {
            return $response->withStatus(422, 'The IP-address for the robot is invalid.');
        }

        // Password for the Nao/Pepper (if used)
        $_SESSION['robotPass'] = $robotPass;

        // Copy files to the robot if appropriate
        if (! empty($robotIp) && ! empty($robotPass)) {
            $o = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR';
            echo "\nCopying files to the robot using the given IP and password...\n";
            echo self::exec("sshpass -p $robotPass ssh $o nao@$robotIp \"mkdir -p /home/nao/cbsr\" && echo \"OK (1/4)\"");
            $files = ["$path/start.sh", "$path/stop.sh", "$path/video_producer.py", "$path/event_producer.py",
                "$path/audio_producer.py", "$path/action_consumer.py", "$path/audio_consumer.py", "$path/tablet.py", "$path/tablet_consumer.py",
				"$path/transformation.py"];
			$selfSigned = $_ENV['DB_SSL_SELFSIGNED'] ?? '';
			if ($selfSigned === '1') {
				$files[] = "$path/cert.pem";
			}
            $scp = '';
            foreach ($files as $file) {
                $scp .= "sshpass -p $robotPass scp $o -p $file nao@$robotIp:/home/nao/cbsr/ &&";
            }
            echo self::exec($scp . 'echo "OK (2/4)"');
            echo self::exec("sshpass -p $robotPass ssh $o nao@$robotIp bash -lc /home/nao/cbsr/stop.sh && echo \"OK (3/4)\"");
            echo self::exec("sshpass -p $robotPass ssh $o nao@$robotIp bash -lc /home/nao/cbsr/start.sh && echo \"OK (4/4)\"");
        }
    }

    public function robotLogs(Request $request, Response $response, $args)
    {
        $robotIp = $_SESSION['robotIp'];
        $robotPass = $_SESSION['robotPass'];
        if (empty($robotIp) || empty($robotPass)) {
            return $response->withStatus(400, 'No robot IP and/or password set.');
        } else {
            $o = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR';
            $logs = ['action_consumer', 'audio_consumer', 'audio_producer', 'event_producer', 'tablet_consumer', 'video_producer'];
            foreach ($logs as $log) {
                echo "<br><b>$log</b><br>";
                echo self::exec("sshpass -p $robotPass ssh $o nao@$robotIp cat /home/nao/cbsr/$log.log");
            }
        }
    }

    public function robotDisconnect(Request $request, Response $response, $args)
    {
        $robotIp = $_SESSION['robotIp'];
        $robotPass = $_SESSION['robotPass'];
        if (empty($robotIp) || empty($robotPass)) {
            return $response->withStatus(400, 'No robot IP and/or password set.');
        } else {
            $o = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR';
            echo self::exec("sshpass -p $robotPass ssh $o nao@$robotIp bash --login -c /home/nao/cbsr/stop.sh && echo \"OK (1/2)\"");
            echo self::exec("sshpass -p $robotPass ssh $o nao@$robotIp rm -rf /home/nao/cbsr && echo \"OK (2/2)\"");
        }
    }

    /**
     * Execute a command and return it's output.
     * Either wait until the command exits or the timeout has expired.
     *
     * @param string $cmd
     *            Command to execute.
     * @param number $timeout
     *            Timeout in seconds.
     * @return string Output of the command.
     * @throws \Exception
     */
    private static function exec($cmd, $timeout = 60)
    {
        $descriptors = [
            [
                'pipe',
                'r'
            ],
            [
                'pipe',
                'w'
            ],
            [
                'pipe',
                'w'
            ]
        ];
        $process = proc_open($cmd, $descriptors, $pipes);
        if (! is_resource($process)) {
            throw new \Exception('Could not execute process');
        }

        // Set the stdout and stderr streams to non-blocking.
        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);
        // Turn the timeout into microseconds.
        $timeout = $timeout * 1000000;

        // Output buffer.
        $buffer = '';
        // While we have time to wait.
        while ($timeout > 0) {
            $start = microtime(true);

            // Wait until we have output or the timer expired.
            $read = [
                $pipes[1]
            ];
            $other = [];
            stream_select($read, $other, $other, 0, $timeout);

            // Get the status of the process.
            // Do this before we read from the stream,
            // so we can't lose the last bit of output if the process dies between these functions.
            $status = proc_get_status($process);

            // Read the contents from the buffer.
            // This function will always return immediately as the stream is non-blocking.
            $buffer .= stream_get_contents($pipes[1]);

            // Subtract the number of microseconds that we waited.
            $timeout -= (microtime(true) - $start) * 1000000;

            if (! $status['running']) {
                // Break from this loop if the process exited before the timeout.
                break;
            }
        }

        // Check if there were any errors.
        $errors = stream_get_contents($pipes[2]);
        if ($timeout <= 0) {
            $errors .= PHP_EOL . 'Request timed out!';
        } else if ($status['exitcode'] != 0) {
            $errors .= PHP_EOL . 'Request failed! (code ' . $status['exitcode'] . ')';
        }

        // Kill the process in case the timeout expired and it's still running.
        // If the process already exited this won't do anything.
        proc_terminate($process, 9);

        // Close all streams.
        fclose($pipes[0]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        proc_close($process);

        return empty($errors) ? $buffer : $errors;
    }
}