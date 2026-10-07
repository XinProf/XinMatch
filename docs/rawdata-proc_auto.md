# Automatic Raw Data Processing

## Automatic Raw Data Processing
As has already been mentioned in the introduction to raw data processing, a variety of steps is required to obtain peak data of sufficient quality from the raw/profile diffraction data. While you can do this step by step manually by executing the corresponding commands in the "Pattern" menu (or using the main toolbar buttons), Match! is also able to perform the required tasks automatically in a single step.
In order to use this facility, simply execute the "Autom. raw data proc." command from the "Pattern/Automatic" submenu, press the corresonding keyboard shortcut <Ctrl+A>, or press the corresponding button  in the main toolbar.
You can define which actions shall be taken during the automatic raw data processing in the corresponding Options dialog page which can either be opened by selecting "Configure..." from the "Pattern/Automatic" submenu, by pressing the corresonding keyboard shortcut <Ctrl+Alt+A>, or by pressing the corresponding button  in the main toolbar.
By default, Match! will first strip the alpha2-radiation. Afterwards, the background will be subtracted, and the data will be smoothed subsequently. The conventional peak search will be performed "implicitly", i.e. without any user interaction (using the current peak search sensitivity). Finally, Match! will try to correct a possible zero point error.
Note:
- The automatic raw data processing is invoked automatically by the search-match routine if only raw (profile) but no peak data are present when the search-match is executed.