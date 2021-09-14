var socket = null;
$(window).on('load', function() {
	var body = $(document.body);
	body.html('+');
	socket = new WebSocket('ws://' + window.location.hostname + ':8001');
	socket.onopen = function() {
		body.html('*');
	};
	socket.onmessage = function(event) {
		var data = JSON.parse(event.data);
		if( data.chan == 'render_html' ) {
			body.html(data.msg);
			updateListeningIcon('ListeningDone');
			vuLogo();
			englishFlag();
			activateButtons();
			chatBox();
			activateSorting();
		} else if( data.chan == 'events' ) {
			updateListeningIcon(data.msg);
		} else if( data.chan == 'text_transcript' ) {
			updateSpeechText(data.msg);
		} else {
			alert(data.chan + ': ' + data.msg);
		}
	};
	socket.onerror = function(error) {
		if( error.message ) alert(error.message);
		else alert(error);
	};
	socket.onclose = function() {
		body.html('');
	};
});
$(window).on('unload', function() {
	if( socket ) socket.close();
});

var iconStyle = 'style="height:10vh"';
function updateListeningIcon(input) {
	if( input == 'ListeningStarted' ) {
		$('.listening_icon').html('<img src="img/listening.png" '+iconStyle+'>');
		updateSpeechText(''); // clear it
	} else if( input == 'ListeningDone' ) {
		$('.listening_icon').html('<img src="img/not_listening.png" '+iconStyle+'>');
	}
}
function updateSpeechText(input) {
	$('.speech_text').html(input);
}
function vuLogo() {
	$('.vu_logo').html('<img src="img/vu_logo.png" '+iconStyle+'>');
}
function englishFlag() {
	var englishFlag = $('.english_flag');
	englishFlag.html('<img src="img/english_flag.png" '+iconStyle+'>');
	englishFlag.click(function() {
		socket.send('audio_language|en-US');
		socket.send('dialogflow_language|en-US');
	});
}
function activateButtons() {
	$(':button').click(function() {
		var dataValue = $(this).children().data('value');
		if( dataValue ) {
			socket.send('browser_button|'+dataValue);
		} else {
			var txt = document.createElement('textarea');
			txt.innerHTML = $(this).html();
			socket.send('browser_button|'+txt.value);
		}
	});
}
function chatBox() {
	var chatBox = $('.chatbox');
	chatBox.html('<form><input id="chatbox-input" type="text" autofocus class="w-25"><input type="submit"></form>');
	var chatBoxInput = $("#chatbox-input");
	chatBoxInput.focus();

	chatBox.submit(function(e) {
		var text = chatBoxInput.val();
		socket.send('action_chat|'+text);
		chatBoxInput.val('');
		e.preventDefault();
	});
}
function activateSorting() {
	var currentSort = [];
	var sortItems = $('.sortitem');
	sortItems.click(function() {
		var $this = $(this);
		var id = $this.attr('id');
		var label = $this.find('.card-text');
		if( currentSort.length > 0 && id == currentSort[currentSort.length-1] ) {
			currentSort.pop();
			label.html('');
		} else if( label.html() == '' ) {
			currentSort.push(id);
			label.html(currentSort.length)
		}
	});
	sortItems.parent().parent().after('<form class="mt-3"><input type="submit" value="Klaar!"></form>');
	$('form').submit(function(e) {
		socket.send('browser_button|'+JSON.stringify(currentSort));
		currentSort = [];
		e.preventDefault();
	});
}