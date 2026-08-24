/**
 * FC Othmarsingen - inoffizielle App zum Matchcenter des AFV.
 *
 * Aufbau: drei Tabs (Übersicht, Spiele, Statistik), darüber ein Stack für
 * die Detailseiten von Team und Spiel.
 */
import { Ionicons } from '@expo/vector-icons';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import HomeScreen from './src/screens/HomeScreen';
import MatchScreen from './src/screens/MatchScreen';
import MatchesScreen from './src/screens/MatchesScreen';
import StatsScreen from './src/screens/StatsScreen';
import TeamScreen from './src/screens/TeamScreen';
import { colors } from './src/theme';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Übersicht: 'home',
  Spiele: 'football',
  Statistik: 'stats-chart',
};

function Tabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textFaint,
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={ICONS[route.name] ?? 'ellipse'} color={color} size={size} />
        ),
      })}
    >
      <Tab.Screen name="Übersicht" component={HomeScreen} />
      <Tab.Screen name="Spiele" component={MatchesScreen} />
      <Tab.Screen name="Statistik" component={StatsScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <StatusBar style="light" />
        <Stack.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: colors.dark },
            headerTintColor: '#fff',
            headerTitleStyle: { fontWeight: '700' },
          }}
        >
          <Stack.Screen name="Start" component={Tabs} options={{ headerShown: false }} />
          <Stack.Screen
            name="Team"
            component={TeamScreen}
            options={({ route }) => ({ title: (route.params as any)?.title ?? 'Team' })}
          />
          <Stack.Screen name="Spiel" component={MatchScreen} options={{ title: 'Spiel' }} />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
