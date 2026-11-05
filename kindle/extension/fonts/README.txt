Nunito (SIL Open Font License 1.1, https://openfontlicense.org), weights 400/700/800/900, from @fontsource/nunito
5.3.0 (the same files the server uses), converted from WOFF to TTF and renamed to the family "Kiosk Nunito".
bin/fonts.sh registers this folder with the Kindle's fontconfig (90-paperkiosk.conf -> /var/local/font/conf.d),
so the kiosk pages use it as a system font instead of downloading a web font on every page load.
