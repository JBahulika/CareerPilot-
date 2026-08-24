plugins {
    id("com.android.application")
}

android {
    namespace = "com.careerpilot.remote"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.careerpilot.remote"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.10.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.webkit:webkit:1.10.0")
}
